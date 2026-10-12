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
            if (LiveCubeFeed.Read(8192).Count!=4) throw new Exception("Live feed region filter failed");
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
        Cv2.ImWrite(Path.Combine(AppContext.BaseDirectory,"projection-validation.png"),screenshot);
        File.WriteAllText(Path.Combine(AppContext.BaseDirectory,"self-test-result.json"),JsonSerializer.Serialize(new { passed=true,result.Confidence,result.MatchCount,projectedX=point.X,projectedY=point.Y,expected=383.6 }));
    }
}
