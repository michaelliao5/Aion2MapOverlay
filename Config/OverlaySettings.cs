namespace Aion2MapOverlay.Config;

public static class OverlaySettings
{
    public const int FramesPerSecond = 2;
    public const double MinMatchConfidence = 0.5;

    public static class Markers
    {
        public const double Size = 16.0;
        public const double StrokeThickness = 2.0;
        public static readonly (byte R, byte G, byte B) MonolithColor = (255, 0, 255);
        public static readonly (byte R, byte G, byte B) HiddenCubeColor = (0, 255, 255);
    }
}

public static class MatcherSettings
{
    public const int MaxFeatures = 16000;
    public const float RatioThreshold = 0.7f;
    public const int MinMatchCount = 10;
    public const double ReprojectionThreshold = 5.0;
    public const double EarlyExitConfidence = 0.7;
    public static readonly double[] PyramidScales = [0.5, 0.35, 0.25, 0.2, 0.15, 0.125, 0.1];

    public static class UIMask
    {
        public const double TopMaskPercent = 0.05;
        public const double RightMaskPercent = 0.034;
    }

    public static class Validation
    {
        public const double MinInlierRatio = 0.3;
        public const double MinAreaRatio = 0.01;
        public const double MaxAreaRatio = 100.0;
        public const double MaxAspectDeviation = 0.5;
        public const int CornerBoundsTolerance = 100;
    }
}
