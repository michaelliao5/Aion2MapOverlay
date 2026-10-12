namespace Aion2MapOverlay;

public partial class App : System.Windows.Application
{
    protected override void OnStartup(System.Windows.StartupEventArgs e)
    {
        base.OnStartup(e);
        int stateIndex = Array.IndexOf(e.Args, "--state");
        if (stateIndex >= 0 && stateIndex + 1 < e.Args.Length)
            LiveCubeFeed.StatePath = System.IO.Path.GetFullPath(e.Args[stateIndex + 1]);
        if (e.Args.Contains("--match-recording"))
        {
            int index = Array.IndexOf(e.Args, "--match-recording");
            using var frame = OpenCvSharp.Cv2.ImRead(e.Args[index+1], OpenCvSharp.ImreadModes.Grayscale);
            using var reference = ResourceLoader.LoadMapImage(Models.Faction.Elyos);
            using var matcher = new RobustMapMatcher(reference);
            using var result = matcher.MatchCornerMap(frame);
            System.IO.File.WriteAllText(System.IO.Path.Combine(AppContext.BaseDirectory, "recorded-match.json"), System.Text.Json.JsonSerializer.Serialize(new { matched = result != null && result.Confidence >= Config.OverlaySettings.MinMatchConfidence && result.MatchCount >= Config.MatcherSettings.MinMatchCount, confidence = result?.Confidence, matches = result?.MatchCount, offsetX = result?.OffsetX, offsetY = result?.OffsetY, diagnostics = matcher.Diagnostics }));
            Shutdown(result == null ? 1 : 0); return;
        }
        if (e.Args.Contains("--diagnose"))
        {
            using var frame = ScreenCapture.CaptureScreen();
            OpenCvSharp.Cv2.ImWrite(System.IO.Path.Combine(AppContext.BaseDirectory, "captured-map.png"), frame);
            Shutdown(0);
            return;
        }
        if (e.Args.Contains("--self-test"))
        {
            try { OverlaySelfTest.Run(); Shutdown(0); }
            catch (Exception ex) { System.IO.File.WriteAllText(System.IO.Path.Combine(AppContext.BaseDirectory,"self-test-error.txt"),ex.ToString()); Shutdown(1); }
            return;
        }
        var window = new OverlayWindow(Models.Faction.Elyos, new Models.MarkerFilter { ShowHiddenCube = true });
        MainWindow = window;
        window.Show();
    }
}
