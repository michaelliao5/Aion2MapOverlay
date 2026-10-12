using Aion2MapOverlay.Config;
using OpenCvSharp;
using OpenCvSharp.Features2D;
using CvSize = OpenCvSharp.Size;

namespace Aion2MapOverlay;

public class RobustMapMatcher : IDisposable
{
    private readonly SIFT _sift;
    private readonly FlannBasedMatcher _matcher;
    private readonly List<PyramidLevel> _pyramid = [];

    public int MapSize { get; private set; }
    public List<string> Diagnostics { get; } = [];

    public RobustMapMatcher(Mat referenceMap)
    {
        _sift = SIFT.Create(nFeatures: MatcherSettings.MaxFeatures);
        _matcher = new FlannBasedMatcher();
        MapSize = Math.Max(referenceMap.Width, referenceMap.Height);

        BuildPyramid(referenceMap);
    }

    private void BuildPyramid(Mat referenceMap)
    {
        var scales = MatcherSettings.PyramidScales;

        using var refGray = new Mat();
        Cv2.CvtColor(referenceMap, refGray, ColorConversionCodes.BGR2GRAY);

        foreach (var scale in scales)
        {
            var scaledMap = new Mat();
            Cv2.Resize(refGray, scaledMap, new CvSize(), scale, scale);

            var descriptors = new Mat();
            _sift.DetectAndCompute(scaledMap, null, out var keypoints, descriptors);

            var level = new PyramidLevel
            {
                Scale = scale,
                Image = scaledMap,
                Keypoints = keypoints,
                Descriptors = descriptors
            };

            _pyramid.Add(level);
        }
    }

    public MatchResult? MatchCornerMap(Mat screenshotGray)
    {
        // Match the transparent map without spending the feature budget on the 3D scene.
        int x = (int)(screenshotGray.Width * 0.78);
        int y = (int)(screenshotGray.Height * 0.63);
        int right = (int)(screenshotGray.Width * 0.995);
        int bottom = (int)(screenshotGray.Height * 0.98);
        using var mapArea = new Mat(screenshotGray, new Rect(x, y, right-x, bottom-y));
        var result = Match(mapArea);
        if (result != null) { result.OffsetX = x; result.OffsetY = y; }
        return result;
    }

    public MatchResult? Match(Mat screenshotGray)
    {
        if (screenshotGray.Empty())
            return null;

        Diagnostics.Clear();
        using var uiMask = CreateSimpleUIMask(screenshotGray);

        using var queryDescriptors = new Mat();
        _sift.DetectAndCompute(screenshotGray, uiMask, out var queryKeypoints, queryDescriptors);

        if (queryDescriptors.Empty() || queryKeypoints.Length < MatcherSettings.MinMatchCount)
        {
            return null;
        }

        MatchResult? bestResult = null;
        double bestScore = 0;

        foreach (var level in _pyramid)
        {
            if (level.Descriptors.Empty())
                continue;

            var result = TryMatchLevel(screenshotGray, queryKeypoints, queryDescriptors, level);

            if (result != null && result.Confidence > bestScore)
            {
                bestResult?.Dispose();
                bestScore = result.Confidence;
                bestResult = result;

                if (bestScore > MatcherSettings.EarlyExitConfidence)
                    break;
            }
            else
            {
                result?.Dispose();
            }
        }

        return bestResult;
    }

    private Mat CreateSimpleUIMask(Mat image)
    {
        var mask = new Mat(image.Size(), MatType.CV_8UC1, new Scalar(255));

        int topMask = (int)(image.Height * MatcherSettings.UIMask.TopMaskPercent);
        int rightMask = (int)(image.Width * MatcherSettings.UIMask.RightMaskPercent);

        Cv2.Rectangle(mask, new Rect(0, 0, image.Width, topMask), new Scalar(0), -1);
        Cv2.Rectangle(mask, new Rect(image.Width - rightMask, 0, rightMask, image.Height), new Scalar(0), -1);

        return mask;
    }

    private MatchResult? TryMatchLevel(Mat screenshot, KeyPoint[] queryKeypoints, Mat queryDescriptors, PyramidLevel level)
    {
        var matches = _matcher.KnnMatch(queryDescriptors, level.Descriptors, 2);

        var goodMatches = new List<DMatch>();
        foreach (var match in matches)
        {
            if (match.Length >= 2 && match[0].Distance < MatcherSettings.RatioThreshold * match[1].Distance)
            {
                goodMatches.Add(match[0]);
            }
        }

        Diagnostics.Add($"scale:{level.Scale} good:{goodMatches.Count}");
        if (goodMatches.Count < MatcherSettings.MinMatchCount)
            return null;

        var srcPts = goodMatches.Select(m => queryKeypoints[m.QueryIdx].Pt).ToArray();
        var dstPts = goodMatches.Select(m => level.Keypoints[m.TrainIdx].Pt).ToArray();

        Mat? homography = null;
        using var inlierMask = new Mat();

        try
        {
            homography = Cv2.FindHomography(
                InputArray.Create(srcPts),
                InputArray.Create(dstPts),
                HomographyMethods.Ransac,
                MatcherSettings.ReprojectionThreshold,
                inlierMask
            );
        }
        catch (OpenCVException ex)
        {
            System.Diagnostics.Debug.WriteLine($"[RobustMapMatcher] Homography calculation failed: {ex.Message}");
            return null;
        }

        if (homography == null || homography.Empty())
        {
            homography?.Dispose();
            return null;
        }

        var validation = ValidateHomography(homography, screenshot.Size(), level.Image.Size(), inlierMask);

        Diagnostics.Add($"valid:{validation.IsValid} inlier:{validation.InlierRatio:F2}");
        if (!validation.IsValid)
        {
            homography.Dispose();
            return null;
        }

        var confidence = ComputeConfidence(
            goodMatches.Count,
            validation.InlierRatio,
            validation.GeometricScore,
            validation.ReprojError
        );

        if (confidence < OverlaySettings.MinMatchConfidence)
        {
            homography.Dispose();
            return null;
        }

        return new MatchResult
        {
            Homography = homography,
            HomographyInverse = homography.Inv(),
            Scale = level.Scale,
            Confidence = confidence,
            MatchCount = goodMatches.Count,
            ScreenSize = screenshot.Size()
        };
    }

    private ValidationResult ValidateHomography(Mat H, CvSize querySize, CvSize refSize, Mat? inlierMask)
    {
        var result = new ValidationResult { IsValid = false };

        try
        {
            var queryCorners = new Point2f[]
            {
                new(0, 0),
                new(querySize.Width, 0),
                new(querySize.Width, querySize.Height),
                new(0, querySize.Height)
            };

            var refCorners = Cv2.PerspectiveTransform(queryCorners, H);

            var tolerance = MatcherSettings.Validation.CornerBoundsTolerance;
            foreach (var corner in refCorners)
            {
                if (corner.X < -tolerance || corner.X > refSize.Width + tolerance ||
                    corner.Y < -tolerance || corner.Y > refSize.Height + tolerance)
                {
                    return result;
                }
            }

            if (!IsConvexQuad(refCorners))
                return result;

            double queryArea = querySize.Width * querySize.Height;
            double refArea = ComputeQuadArea(refCorners);
            double areaRatio = refArea / queryArea;

            if (areaRatio < MatcherSettings.Validation.MinAreaRatio ||
                areaRatio > MatcherSettings.Validation.MaxAreaRatio)
                return result;

            double queryAspect = (double)querySize.Width / querySize.Height;
            double refAspect = ComputeQuadAspect(refCorners);

            if (Math.Abs(queryAspect - refAspect) > MatcherSettings.Validation.MaxAspectDeviation)
                return result;

            int inlierCount = 0;
            if (inlierMask != null && !inlierMask.Empty())
            {
                for (int i = 0; i < inlierMask.Rows; i++)
                {
                    if (inlierMask.At<byte>(i) != 0)
                        inlierCount++;
                }
            }

            double inlierRatio = inlierMask != null && inlierMask.Rows > 0
                ? (double)inlierCount / inlierMask.Rows
                : 0;

            if (inlierRatio < MatcherSettings.Validation.MinInlierRatio)
                return result;

            result.IsValid = true;
            result.InlierRatio = inlierRatio;
            result.GeometricScore = ComputeGeometricScore(refCorners, queryAspect);
            result.ReprojError = 2.0;
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"[RobustMapMatcher] Homography validation failed: {ex.Message}");
            return result;
        }

        return result;
    }

    private double ComputeConfidence(int matchCount, double inlierRatio, double geometricScore, double reprojError)
    {
        double matchScore = Math.Min(matchCount / 100.0, 1.0) * 0.3;
        double inlierScore = inlierRatio * 0.3;
        double geoScore = geometricScore * 0.25;
        double errorScore = Math.Max(0, 1.0 - reprojError / 10.0) * 0.15;

        return Math.Clamp(matchScore + inlierScore + geoScore + errorScore, 0, 1);
    }

    private bool IsConvexQuad(Point2f[] corners)
    {
        if (corners.Length != 4)
            return false;

        int sign = 0;
        for (int i = 0; i < 4; i++)
        {
            var v1 = corners[(i + 1) % 4] - corners[i];
            var v2 = corners[(i + 2) % 4] - corners[(i + 1) % 4];
            double cross = v1.X * v2.Y - v1.Y * v2.X;

            if (Math.Abs(cross) > 1e-6)
            {
                int currentSign = cross > 0 ? 1 : -1;
                if (sign == 0)
                    sign = currentSign;
                else if (sign != currentSign)
                    return false;
            }
        }
        return true;
    }

    private double ComputeQuadArea(Point2f[] corners)
    {
        double area = 0;
        for (int i = 0; i < 4; i++)
        {
            int j = (i + 1) % 4;
            area += corners[i].X * corners[j].Y;
            area -= corners[j].X * corners[i].Y;
        }
        return Math.Abs(area) / 2;
    }

    private double ComputeQuadAspect(Point2f[] corners)
    {
        double width = (Distance(corners[0], corners[1]) + Distance(corners[3], corners[2])) / 2;
        double height = (Distance(corners[0], corners[3]) + Distance(corners[1], corners[2])) / 2;
        return height > 0 ? width / height : 1;
    }

    private double Distance(Point2f a, Point2f b)
    {
        return Math.Sqrt(Math.Pow(a.X - b.X, 2) + Math.Pow(a.Y - b.Y, 2));
    }

    private double ComputeGeometricScore(Point2f[] refCorners, double expectedAspect)
    {
        double actualAspect = ComputeQuadAspect(refCorners);
        double aspectScore = 1.0 - Math.Min(Math.Abs(actualAspect - expectedAspect) / expectedAspect, 1.0);
        double convexScore = IsConvexQuad(refCorners) ? 1.0 : 0.0;

        return (aspectScore + convexScore) / 2;
    }

    public void Dispose()
    {
        _sift.Dispose();
        _matcher.Dispose();
        foreach (var level in _pyramid)
        {
            level.Image.Dispose();
            level.Descriptors.Dispose();
        }
    }
}

public class PyramidLevel
{
    public double Scale { get; set; }
    public Mat Image { get; set; } = new();
    public KeyPoint[] Keypoints { get; set; } = [];
    public Mat Descriptors { get; set; } = new();
}

public class MatchResult : IDisposable
{
    public Mat? Homography { get; set; }
    public Mat? HomographyInverse { get; set; }
    public double Scale { get; set; }
    public double Confidence { get; set; }
    public int MatchCount { get; set; }
    public CvSize ScreenSize { get; set; }
    public int OffsetX { get; set; }
    public int OffsetY { get; set; }

    public void Dispose()
    {
        Homography?.Dispose();
        HomographyInverse?.Dispose();
    }
}

public struct ValidationResult
{
    public bool IsValid;
    public double InlierRatio;
    public double GeometricScore;
    public double ReprojError;
}

