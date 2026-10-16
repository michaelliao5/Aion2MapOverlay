using Aion2MapOverlay.Config;
using Aion2MapOverlay.Models;
using OpenCvSharp;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Threading;
using YamlDotNet.Serialization;
using ContextMenuStrip = System.Windows.Forms.ContextMenuStrip;
using NotifyIcon = System.Windows.Forms.NotifyIcon;
using ToolStripMenuItem = System.Windows.Forms.ToolStripMenuItem;
using WpfBrushes = System.Windows.Media.Brushes;
using WpfColor = System.Windows.Media.Color;
using WpfMessageBox = System.Windows.MessageBox;
using WpfMessageBoxButton = System.Windows.MessageBoxButton;
using WpfMessageBoxImage = System.Windows.MessageBoxImage;
using WpfRoutedEventArgs = System.Windows.RoutedEventArgs;
using WpfSolidColorBrush = System.Windows.Media.SolidColorBrush;

namespace Aion2MapOverlay;

public partial class OverlayWindow : System.Windows.Window
{
    private Faction _faction;
    private MarkerFilter _filter;
    private RobustMapMatcher? _matcher;
    private List<(double LeafletX, double LeafletY, string Name, string Subtype)> _markers = [];
    private readonly DispatcherTimer _timer;
    private readonly List<System.Windows.UIElement> _markerElements = [];
    private NotifyIcon? _trayIcon;
    private ContextMenuStrip? _trayContextMenu;
    private System.Drawing.Icon? _trayIconImage;
    private ToolStripMenuItem? _elyosMenuItem;
    private ToolStripMenuItem? _asmodiansMenuItem;
    private ToolStripMenuItem? _abyssMenuItem;

    private static readonly WpfColor MonolithColor = WpfColor.FromRgb(
        OverlaySettings.Markers.MonolithColor.R,
        OverlaySettings.Markers.MonolithColor.G,
        OverlaySettings.Markers.MonolithColor.B);
    private static readonly WpfColor HiddenCubeColor = WpfColor.FromRgb(
        OverlaySettings.Markers.HiddenCubeColor.R,
        OverlaySettings.Markers.HiddenCubeColor.G,
        OverlaySettings.Markers.HiddenCubeColor.B);
    private static readonly IDeserializer YamlDeserializer = new DeserializerBuilder()
        .IgnoreUnmatchedProperties()
        .Build();

    private object? _lastCandidateDiagnostic;
    private int _frameCount;
    private DateTime _lastFpsUpdate = DateTime.Now;
    private double _currentFps;

    public OverlayWindow(Faction faction, MarkerFilter filter)
    {
        InitializeComponent();

        _faction = faction;
        _filter = filter;

        _timer = new DispatcherTimer
        {
            Interval = TimeSpan.FromSeconds(1.0 / OverlaySettings.FramesPerSecond)
        };
        _timer.Tick += Timer_Tick;

        Loaded += OverlayWindow_Loaded;
        Closing += OverlayWindow_Closing;
    }

    private void OverlayWindow_Loaded(object sender, WpfRoutedEventArgs e)
    {
        SetupTransparentWindow();

        string factionName = _faction switch
        {
            Faction.Elyos => "ELYOS (천족/天族)",
            Faction.Asmodians => "ASMODIANS (마족/魔族)",
            Faction.Abyss => "ABYSS (심연/深淵)",
            _ => "UNKNOWN"
        };


        LoadData();
        _timer.Start();
        SetupTrayIcon();
    }

    private void SetupTrayIcon()
    {
        _trayContextMenu = new ContextMenuStrip();

        _elyosMenuItem = new ToolStripMenuItem("Elyos (천족/天族)");
        _elyosMenuItem.Click += (s, e) => ChangeFaction(Faction.Elyos);
        _trayContextMenu.Items.Add(_elyosMenuItem);

        _asmodiansMenuItem = new ToolStripMenuItem("Asmodians (마족/魔族)");
        _asmodiansMenuItem.Enabled = false;
        _asmodiansMenuItem.Click += (s, e) => ChangeFaction(Faction.Asmodians);
        _trayContextMenu.Items.Add(_asmodiansMenuItem);

        _abyssMenuItem = new ToolStripMenuItem("Abyss (심연/深淵)");
        _abyssMenuItem.Enabled = false;
        _abyssMenuItem.Click += (s, e) => ChangeFaction(Faction.Abyss);
        _trayContextMenu.Items.Add(_abyssMenuItem);

        UpdateFactionMenuChecks();

        _trayContextMenu.Items.Add(new System.Windows.Forms.ToolStripSeparator());

        var exitItem = new ToolStripMenuItem("Exit");
        exitItem.Click += (s, e) => Dispatcher.Invoke(Close);
        _trayContextMenu.Items.Add(exitItem);

        _trayIconImage = ResourceLoader.LoadIcon();

        _trayIcon = new NotifyIcon
        {
            Icon = _trayIconImage,
            Visible = true,
            Text = $"Aion2 Map Overlay - {_faction}",
            ContextMenuStrip = _trayContextMenu
        };
    }

    private void UpdateFactionMenuChecks()
    {
        if (_elyosMenuItem != null)
            _elyosMenuItem.Checked = _faction == Faction.Elyos;
        if (_asmodiansMenuItem != null)
            _asmodiansMenuItem.Checked = _faction == Faction.Asmodians;
        if (_abyssMenuItem != null)
            _abyssMenuItem.Checked = _faction == Faction.Abyss;
    }

    private void ChangeFaction(Faction newFaction)
    {
        if (_faction == newFaction)
            return;

        _faction = newFaction;

        string factionName = _faction switch
        {
            Faction.Elyos => "ELYOS (천족/天族)",
            Faction.Asmodians => "ASMODIANS (마족/魔族)",
            Faction.Abyss => "ABYSS (심연/深淵)",
            _ => "UNKNOWN"
        };

        Dispatcher.Invoke(() =>
        {
    
            ClearMarkers();
        });

        if (_trayIcon != null)
            _trayIcon.Text = $"Aion2 Map Overlay - {_faction}";
        UpdateFactionMenuChecks();

        _matcher?.Dispose();
        LoadData();
    }

    private void SetupTransparentWindow()
    {
        var hwnd = new WindowInteropHelper(this).Handle;

        var exStyle = NativeMethods.GetWindowLongPtr(hwnd, NativeMethods.GWL_EXSTYLE);
        var newStyle = new IntPtr(exStyle.ToInt64() | NativeMethods.WS_EX_TRANSPARENT | NativeMethods.WS_EX_TOOLWINDOW);
        NativeMethods.SetWindowLongPtr(hwnd, NativeMethods.GWL_EXSTYLE, newStyle);

        NativeMethods.SetWindowPos(
            hwnd,
            NativeMethods.HWND_TOPMOST,
            0, 0, 0, 0,
            NativeMethods.SWP_NOMOVE | NativeMethods.SWP_NOSIZE);
    }

    private void LoadData()
    {
        try
        {
            using var mapImage = ResourceLoader.LoadMapImage(_faction);
            _matcher = new RobustMapMatcher(mapImage);

            var yaml = ResourceLoader.LoadMarkerYaml(_faction);
            var markerFile = YamlDeserializer.Deserialize<MarkerFileData>(yaml);

            _markers = []; // Live packet detections replace static potential spawn pins.
        }
        catch (Exception ex)
        {
            WpfMessageBox.Show($"Failed to load data:\n{ex.Message}", "Error", WpfMessageBoxButton.OK, WpfMessageBoxImage.Error);
        }
    }

    private void Timer_Tick(object? sender, EventArgs e)
    {
        _frameCount++;

        try
        {
            _markers = LiveCubeFeed.Read(_matcher?.MapSize ?? 8192);
            UpdateCubeBanner();
            if (!LiveCubeFeed.Ready || _markers.Count == 0 || _matcher == null)
            {
                ClearMarkers();
                UpdateStatus(0, 0, LiveCubeFeed.Status);
                return;
            }
            using var screenshot = ScreenCapture.CaptureScreen();

            if (screenshot.Empty())
            {
                ClearMarkers();
                UpdateStatus(0, 0, "No capture");
                return;
            }

            using var result = _matcher.MatchCornerMap(screenshot);

            if (result != null && result.Confidence >= OverlaySettings.MinMatchConfidence && result.MatchCount >= MatcherSettings.MinMatchCount)
            {
                var screenMarkers = ProjectMarkersWithSubtype(result);

                UpdateOverlay(screenMarkers, result.Confidence);
                _lastCandidateDiagnostic = new { at = DateTimeOffset.UtcNow, candidates = _markers.Count, drawn = screenMarkers.Count, matches = result.MatchCount, confidence = result.Confidence, reason = screenMarkers.Count == 0 ? "Projected outside visible map; check calibration or map pan" : "Drawn", mapOffsetX = result.OffsetX, mapOffsetY = result.OffsetY };
                UpdateStatus(result.MatchCount, result.Confidence, LiveCubeFeed.Status + $" | {screenMarkers.Count} drawn" + (screenMarkers.Count == 0 ? " | outside visible map" : ""));
            }
            else
            {
                ClearMarkers();
                _lastCandidateDiagnostic = new { at = DateTimeOffset.UtcNow, candidates = _markers.Count, drawn = 0, matches = result?.MatchCount ?? 0, confidence = result?.Confidence ?? 0, reason = "Map not matched" };
                UpdateStatus(
                    result?.MatchCount ?? 0,
                    result?.Confidence ?? 0,
                    $"Map not matched (M:{result?.MatchCount ?? 0}, C:{result?.Confidence ?? 0:P0})"
                );
            }
        }
        catch (Exception ex)
        {
            ClearMarkers();
            UpdateStatus(0, 0, "Overlay error: " + ex.Message);
        }

        UpdateFps();
    }

    private List<(float X, float Y, string Name, string Subtype)> ProjectMarkersWithSubtype(MatchResult result)
    {
        var screenMarkers = new List<(float X, float Y, string Name, string Subtype)>();

        if (result.HomographyInverse == null)
            return screenMarkers;

        var H_inv = result.HomographyInverse;
        var scale = result.Scale;

        foreach (var marker in _markers)
        {
            double imageX = marker.LeafletX;
            double imageY = _matcher!.MapSize - marker.LeafletY;

            double scaledX = imageX * scale;
            double scaledY = imageY * scale;

            var refPoint = new Point2f[] { new((float)scaledX, (float)scaledY) };

            try
            {
                var screenPoint = Cv2.PerspectiveTransform(refPoint, H_inv);

                if (screenPoint[0].X >= 0 && screenPoint[0].X < result.ScreenSize.Width &&
                    screenPoint[0].Y >= 0 && screenPoint[0].Y < result.ScreenSize.Height)
                {
                    screenMarkers.Add((screenPoint[0].X + result.OffsetX, screenPoint[0].Y + result.OffsetY, marker.Name, marker.Subtype));
                }
            }
            catch (OpenCvSharp.OpenCVException ex)
            {
                System.Diagnostics.Debug.WriteLine($"[OverlayWindow] Marker projection failed for '{marker.Name}': {ex.Message}");
            }
        }

        return screenMarkers;
    }

    private void UpdateOverlay(List<(float X, float Y, string Name, string Subtype)> markers, double confidence)
    {
        ClearMarkers();

        byte alpha = (byte)(confidence * 255);

        foreach (var marker in markers)
        {
            WpfColor baseColor = marker.Subtype.Equals("liveCube", StringComparison.OrdinalIgnoreCase)
                ? HiddenCubeColor
                : MonolithColor;

            var fillColor = WpfColor.FromArgb(alpha, baseColor.R, baseColor.G, baseColor.B);
            var strokeColor = WpfColor.FromArgb(alpha, 255, 255, 255);

            var markerSize = OverlaySettings.Markers.Size;
            var circle = new System.Windows.Shapes.Ellipse
            {
                Width = markerSize,
                Height = markerSize,
                Fill = new WpfSolidColorBrush(fillColor),
                Stroke = new WpfSolidColorBrush(strokeColor),
                StrokeThickness = OverlaySettings.Markers.StrokeThickness
            };

            var localPoint = PointFromScreen(new System.Windows.Point(marker.X, marker.Y));
            Canvas.SetLeft(circle, localPoint.X - markerSize / 2);
            Canvas.SetTop(circle, localPoint.Y - markerSize / 2);

            OverlayCanvas.Children.Add(circle);
            _markerElements.Add(circle);
        }
    }

    private void ClearMarkers()
    {
        foreach (var element in _markerElements)
        {
            OverlayCanvas.Children.Remove(element);
        }
        _markerElements.Clear();
    }

    private void UpdateStatus(int matchCount, double confidence, string status)
    {
        try { System.IO.File.WriteAllText(System.IO.Path.Combine(AppContext.BaseDirectory, "overlay-status.json"), System.Text.Json.JsonSerializer.Serialize(new { updated_at = DateTimeOffset.UtcNow, matchCount, confidence, status, markerCount = _markerElements.Count, feedPath = LiveCubeFeed.StatePath, lastCandidate = _lastCandidateDiagnostic, bannerVisible = CubeBanner.Visibility == System.Windows.Visibility.Visible, activeCubeCount = LiveCubeFeed.ActiveCubeCount })); } catch (System.IO.IOException) { }

    }

    public bool UpdateCubeBanner()
    {
        CubeBanner.Visibility = LiveCubeFeed.Ready && LiveCubeFeed.ActiveCubeCount > 0 ? System.Windows.Visibility.Visible : System.Windows.Visibility.Collapsed;
        CubeCountText.Text = $"{LiveCubeFeed.ActiveCubeCount} cubes nearby";
        CubeCountText.Visibility = LiveCubeFeed.ActiveCubeCount > 1 ? System.Windows.Visibility.Visible : System.Windows.Visibility.Collapsed;
        return CubeBanner.Visibility == System.Windows.Visibility.Visible;
    }

    public void RenderBannerPreview()
    {
        CubeBanner.Visibility = System.Windows.Visibility.Visible;
        var content = (System.Windows.FrameworkElement)Content;
        content.Measure(new System.Windows.Size(1920,1080));
        content.Arrange(new System.Windows.Rect(0,0,1920,1080));
        content.UpdateLayout();
        var bitmap = new System.Windows.Media.Imaging.RenderTargetBitmap(1920,1080,96,96,System.Windows.Media.PixelFormats.Pbgra32);
        bitmap.Render(content);
        var encoder = new System.Windows.Media.Imaging.PngBitmapEncoder();
        encoder.Frames.Add(System.Windows.Media.Imaging.BitmapFrame.Create(bitmap));
        using var file = System.IO.File.Create(System.IO.Path.Combine(AppContext.BaseDirectory,"banner-preview.png"));
        encoder.Save(file);
    }

    private void UpdateFps()
    {
        var now = DateTime.Now;
        var elapsed = (now - _lastFpsUpdate).TotalSeconds;

        if (elapsed >= 1.0)
        {
            _currentFps = _frameCount / elapsed;
            _frameCount = 0;
            _lastFpsUpdate = now;
        }
    }

    private void OverlayWindow_Closing(object? sender, System.ComponentModel.CancelEventArgs e)
    {
        _timer.Stop();
        _matcher?.Dispose();

        if (_trayIcon != null)
        {
            _trayIcon.Visible = false;
            _trayIcon.Dispose();
        }

        _trayContextMenu?.Dispose();
        _trayIconImage?.Dispose();
    }
}
