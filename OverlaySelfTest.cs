using OpenCvSharp;
using System.IO;
using System.Text.Json;
using Aion2MapOverlay.Models;

namespace Aion2MapOverlay;

public static class OverlaySelfTest
{
    public static void Run()
    {
        var c = new MapCalibration();
        var origin = c.Project(0,0);
        if (Math.Abs(origin.X-4096)>0.01 || Math.Abs(origin.Y-4096)>0.01) throw new Exception("Center projection failed");
        var corner = c.Project(-408000,-408000);
        if (Math.Abs(corner.X)>0.01 || Math.Abs(corner.Y)>0.01) throw new Exception("Corner projection failed");
        string previousPath=LiveCubeFeed.StatePath;
        string testPath=Path.GetTempFileName();
        try
        {
            LiveCubeFeed.StatePath=testPath;
            double now=DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()/1000.0;
            File.WriteAllText(testPath,JsonSerializer.Serialize(new {updated_at=now,running=true,cubes=new[]{new {Entity=1,Type=1200041,X=0,Y=0,Z=0},new {Entity=2,Type=1301199,X=0,Y=0,Z=0},new {Entity=3,Type=1200008,X=0,Y=0,Z=0},new {Entity=4,Type=1200078,X=0,Y=0,Z=0},new {Entity=5,Type=1200040,X=0,Y=0,Z=0}}}));
            if (LiveCubeFeed.Read(8192).Count!=2) throw new Exception("Live feed region filter failed");
            File.WriteAllText(testPath,JsonSerializer.Serialize(new {updated_at=now-30,running=true,cubes=new[]{new {Entity=1,Type=1200041,X=0,Y=0,Z=0}}}));
            if (LiveCubeFeed.Read(8192).Count!=0) throw new Exception("Stale live feed was not hidden");
        }
        finally { LiveCubeFeed.StatePath=previousPath;File.Delete(testPath); }
        using var map = ResourceLoader.LoadMapImage(Faction.Elyos);
        using var matcher = new RobustMapMatcher(map);
        using var crop = new Mat(map,new Rect(3000,3000,2500,2000));
        using var screenshot = new Mat();
        Cv2.Resize(crop,screenshot,new OpenCvSharp.Size(875,700));
        using var gray = new Mat();
        Cv2.CvtColor(screenshot,gray,ColorConversionCodes.BGR2GRAY);
        using var result = matcher.Match(gray);
        if (result?.HomographyInverse is null) throw new Exception("Synthetic map match failed");
        var point = Cv2.PerspectiveTransform(new Point2f[]{ new((float)(origin.X*result.Scale),(float)(origin.Y*result.Scale)) },result.HomographyInverse)[0];
        if (Math.Abs(point.X-383.6)>10 || Math.Abs(point.Y-383.6)>10) throw new Exception($"Projection differs: {point}");
        Cv2.Circle(screenshot,new OpenCvSharp.Point((int)point.X,(int)point.Y),14,new Scalar(0,210,255),3);
        Cv2.PutText(screenshot,"LIVE CUBE (synthetic projection test)",new OpenCvSharp.Point(20,35),HersheyFonts.HersheySimplex,0.65,new Scalar(0,210,255),2);
        // Exercise corner-map matching and crop-to-desktop translation together.
        using var desktop = new Mat(1080,1920,MatType.CV_8UC3,new Scalar(0));
        var cornerRect = new Rect((int)(1920*.78),(int)(1080*.63),(int)(1920*.995)-(int)(1920*.78),(int)(1080*.98)-(int)(1080*.63));
        using var cornerReference = new Mat(map,new Rect(3500,3500,1400,1280));
        using var cornerView = new Mat(desktop,cornerRect);
        Cv2.Resize(cornerReference,cornerView,cornerRect.Size);
        using var desktopGray = new Mat();
        Cv2.CvtColor(desktop,desktopGray,ColorConversionCodes.BGR2GRAY);
        using var cornerResult = matcher.MatchCornerMap(desktopGray);
        if (cornerResult?.HomographyInverse is null || cornerResult.Confidence<0.5) throw new Exception("Corner map match failed");
        var local = Cv2.PerspectiveTransform(new Point2f[]{new((float)(origin.X*cornerResult.Scale),(float)(origin.Y*cornerResult.Scale))},cornerResult.HomographyInverse)[0];
        double desktopX=local.X+cornerResult.OffsetX,desktopY=local.Y+cornerResult.OffsetY;
        double expectedX=cornerRect.X+(4096-3500)*cornerRect.Width/1400.0;
        double expectedY=cornerRect.Y+(4096-3500)*cornerRect.Height/1280.0;
        if (Math.Abs(desktopX-expectedX)>10 || Math.Abs(desktopY-expectedY)>10) throw new Exception("Corner marker offset is incorrect");
        Cv2.Circle(desktop,new OpenCvSharp.Point((int)desktopX,(int)desktopY),10,new Scalar(255,255,0),2);
        Cv2.ImWrite(Path.Combine(AppContext.BaseDirectory,"corner-validation.png"),desktop);
        Cv2.ImWrite(Path.Combine(AppContext.BaseDirectory,"projection-validation.png"),screenshot);
        File.WriteAllText(Path.Combine(AppContext.BaseDirectory,"self-test-result.json"),JsonSerializer.Serialize(new { passed=true,result.Confidence,result.MatchCount,projectedX=point.X,projectedY=point.Y,expected=383.6,cornerConfidence=cornerResult.Confidence,cornerDesktopX=desktopX,cornerDesktopY=desktopY,cornerExpectedX=expectedX,cornerExpectedY=expectedY }));
    }
}
