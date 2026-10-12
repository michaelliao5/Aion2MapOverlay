using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Aion2MapOverlay;

public sealed class MapCalibration
{
    public double ScaleX { get; set; } = 8192.0 / 816000.0;
    public double ScaleY { get; set; } = 8192.0 / 816000.0;
    public double OffsetX { get; set; } = 4096;
    public double OffsetY { get; set; } = 4096;
    public bool Verified { get; set; } = false;
    public (double X, double Y) Project(double x, double y) => (x * ScaleX + OffsetX, y * ScaleY + OffsetY);
}

public sealed class CubeState
{
    [JsonPropertyName("updated_at")] public double UpdatedAt { get; set; }
    [JsonPropertyName("last_message_at")] public double? LastMessageAt { get; set; }
    [JsonPropertyName("running")] public bool Running { get; set; }
    [JsonPropertyName("cubes")] public List<LiveCube> Cubes { get; set; } = [];
}

public sealed class LiveCube
{
    public uint Entity { get; set; }
    public uint Type { get; set; }
    public double X { get; set; }
    public double Y { get; set; }
    public double Z { get; set; }
}

public static class LiveCubeFeed
{
    public static string StatePath { get; set; } = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "cube-probe", "cube_state.json"));
    public static string CalibrationPath => Path.Combine(AppContext.BaseDirectory, "map-calibration.json");
    public static MapCalibration Calibration { get; private set; } = new();
    public static string Status { get; private set; } = "Waiting for detector";
    public static bool Ready { get; private set; }
    private static readonly JsonSerializerOptions Options = new() { PropertyNameCaseInsensitive = true };

    public static List<(double LeafletX, double LeafletY, string Name, string Subtype)> Read(int mapSize)
    {
        Ready = false;
        try
        {
            if (File.Exists(CalibrationPath))
                Calibration = JsonSerializer.Deserialize<MapCalibration>(File.ReadAllText(CalibrationPath), Options) ?? new();
            if (!double.IsFinite(Calibration.ScaleX) || !double.IsFinite(Calibration.ScaleY) || Calibration.ScaleX == 0 || Calibration.ScaleY == 0 || !double.IsFinite(Calibration.OffsetX) || !double.IsFinite(Calibration.OffsetY))
                throw new InvalidDataException("Invalid calibration");
            using var file = new FileStream(StatePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            var state = JsonSerializer.Deserialize<CubeState>(file, Options);
            double age = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0 - (state?.UpdatedAt ?? 0);
            if (state is null || !state.Running || age < -5 || age > 20)
            {
                Status = "Detector stopped or stale";
                return [];
            }
            if (DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0 - (state.LastMessageAt ?? state.UpdatedAt) > 20)
            {
                Status = "Detector running; no recent game packets";
                return [];
            }
            Ready = true;
            var markers = new List<(double, double, string, string)>();
            foreach (var cube in state.Cubes)
            {
                // Only observed Elyos cube types; unconfirmed whitelist disabled.
                if (cube.Type is not (1200039 or 1200040 or 1200041)) continue;
                if (!double.IsFinite(cube.X) || !double.IsFinite(cube.Y) || Math.Abs(cube.X) > 10000000 || Math.Abs(cube.Y) > 10000000) continue;
                var point = Calibration.Project(cube.X, cube.Y);
                if (point.X < 0 || point.Y < 0 || point.X >= mapSize || point.Y >= mapSize) continue;
                markers.Add((point.X, mapSize - point.Y, "Cube candidate", "liveCube"));
            }
            Status = $"{markers.Count} live cube candidate(s)" + (Calibration.Verified ? "" : " | alignment unverified");
            return markers;
        }
        catch (Exception ex) when (ex is IOException or JsonException or UnauthorizedAccessException)
        {
            Status = "Waiting for detector/calibration";
            return [];
        }
    }
}
