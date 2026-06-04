using System.Diagnostics;
using System.Formats.Tar;
using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Threading;

namespace PST.Bootstrapper;

public static class Program
{
    private static SplashWindow? _splash;
    private static Process? _childProcess;
    private static readonly object _lock = new();

    private static readonly string AppVersion = "1.0.0";

    [STAThread]
    public static void Main(string[] args)
    {
        var app = BuildAvaloniaApp();

        _ = Task.Run(() => RunPipelineAsync());

        app.StartWithClassicDesktopLifetime(args);
    }

    public static AppBuilder BuildAvaloniaApp()
    {
        return AppBuilder.Configure<App>()
            .UsePlatformDetect()
            .With(new X11PlatformOptions { EnableMultiTouch = true, UseDBusMenu = false })
            .With(new Win32PlatformOptions())
            .UseSkia();
    }

    private static bool IsWindows => RuntimeInformation.IsOSPlatform(OSPlatform.Windows);
    private static bool IsLinux => RuntimeInformation.IsOSPlatform(OSPlatform.Linux);
    private static bool IsMacOS => RuntimeInformation.IsOSPlatform(OSPlatform.OSX);

    private static readonly bool IsPortable = _DetectPortable();

    private static string GetExeDirectory()
    {
        var path = Environment.ProcessPath
            ?? Assembly.GetEntryAssembly()!.Location;
        return Path.GetDirectoryName(path)
            ?? AppContext.BaseDirectory;
    }

    private static bool _DetectPortable()
    {
        try
        {
            var assembly = Assembly.GetEntryAssembly();
            if (assembly?.GetManifestResourceStream("portable.marker") != null)
                return true;
        }
        catch { }

        try
        {
            var exeDir = GetExeDirectory();
            if (File.Exists(Path.Combine(exeDir, "portable")))
                return true;
        }
        catch { }

        return false;
    }

    private static string GetAppDirectory()
    {
        if (IsPortable)
        {
            return Path.Combine(GetExeDirectory(), "user");
        }

        if (IsWindows)
        {
            var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            return Path.Combine(localAppData, "PST");
        }

        if (IsMacOS)
        {
            var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            return Path.Combine(home, "Library", "Application Support", "PST");
        }

        var homeDir = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        return Path.Combine(homeDir, ".local", "share", "PST");
    }

    private static string GetVenvPython(string appDir)
    {
        return IsWindows
            ? Path.Combine(appDir, ".venv", "Scripts", "python.exe")
            : Path.Combine(appDir, ".venv", "bin", "python");
    }

    private static string GetUvBinaryPath(string appDir)
    {
        return IsWindows
            ? Path.Combine(appDir, "bin", "uv.exe")
            : Path.Combine(appDir, "bin", "uv");
    }

    private static async Task RunPipelineAsync()
    {
        var appDir = GetAppDirectory();
        var exitCode = 0;

        try
        {
            await Task.Delay(300);

            Dispatcher.UIThread.Post(() =>
            {
                _splash = App.Splash;
            });

            await WaitForSplash();

            UpdateProgress(2, "Checking environment...");

            Directory.CreateDirectory(appDir);
            Directory.CreateDirectory(Path.Combine(appDir, "bin"));

            var cacheValid = IsCacheValid(appDir);
            var venvPython = GetVenvPython(appDir);
            var needsSetup = cacheValid == false || !File.Exists(venvPython);

            if (needsSetup)
            {
                UpdateProgress(5, "Extracting files...");
                await ExtractSourcePayloadAsync(appDir);

                UpdateProgress(12, "Preparing runtime...");
                await ExtractUvBinaryAsync(appDir);

                var uvPath = GetUvBinaryPath(appDir);

                UpdateProgress(15, "Installing Python 3.12...");
                await RunUvCommandAsync(uvPath, appDir, "python install 3.12", appDir,
                    pct => UpdateProgress(
                        MapProgress(pct, 15, 30),
                        "Installing Python 3.12..."));

                UpdateProgress(32, "Creating virtual environment...");
                var venvDir = Path.Combine(appDir, ".venv");
                if (Directory.Exists(venvDir))
                {
                    try { Directory.Delete(venvDir, true); } catch { }
                }
                await RunUvCommandAsync(uvPath, appDir, $"venv \"{venvDir}\" --python 3.12", appDir);

                UpdateProgress(35, "Installing dependencies...", "Resolving packages...");
                var reqFile = Path.Combine(appDir, "requirements.txt");
                if (File.Exists(reqFile))
                {
                    lock (_depLock) _depPackagesInstalled = 0;
                    await RunUvCommandAsync(uvPath, appDir, $"pip install -v --no-cache -r \"{reqFile}\"", appDir,
                        pct => UpdateProgress(
                            MapProgress(pct, 35, 85),
                            "Installing dependencies..."),
                        detail => UpdateProgress(
                            MapProgress(
                                EstimateDependencyProgress(detail, reqFile),
                                35, 85),
                            "Installing dependencies...",
                            detail));
                }

                UpdateProgress(88, "Finalizing...");
                WriteCacheHash(appDir);
            }
            else
            {
                UpdateProgress(60, "Using cached environment...");
                await Task.Delay(200);
            }

            UpdateProgress(92, "Starting Palworld Save Tools...");

            if (!File.Exists(venvPython))
            {
                UpdateProgress(0, "Error: Python not found. Please restart.");
                await Task.Delay(5000);
                Shutdown(1);
                return;
            }

            var mainPy = Path.Combine(appDir, "src", "palworld_aio", "main.py");
            if (!File.Exists(mainPy))
            {
                UpdateProgress(0, "Error: Application files not found. Please restart.");
                await Task.Delay(5000);
                Shutdown(1);
                return;
            }

            UpdateProgress(96, "Launching...");
            await Task.Delay(150);

            CloseSplash();

            exitCode = await LaunchApplicationAsync(venvPython, mainPy, appDir);
        }
        catch (Exception ex)
        {
            try
            {
                var logDir = Path.Combine(appDir, "logs");
                Directory.CreateDirectory(logDir);
                await File.WriteAllTextAsync(
                    Path.Combine(logDir, "bootstrapper_error.log"),
                    $"[{DateTime.UtcNow:yyyy-MM-dd HH:mm:ss}] {ex.GetType().Name}: {ex.Message}\n{ex.StackTrace}\n\nInner: {ex.InnerException}\n");
            }
            catch { }

            var shortMsg = ex.Message.Length > 80 ? ex.Message[..80] + "..." : ex.Message;
            UpdateProgress(0, $"Error: {shortMsg}");
            await Task.Delay(6000);
        }

        Shutdown(exitCode);
    }

    private static async Task WaitForSplash()
    {
        for (var i = 0; i < 100; i++)
        {
            if (_splash != null) return;
            await Task.Delay(100);
        }
    }

    private static void UpdateProgress(int percent, string status, string? detail = null)
    {
        _splash?.UpdateProgress(percent, status, detail);
    }

    private static void CloseSplash()
    {
        try { _splash?.CloseSplash(); } catch { }
    }

    private static async Task ExtractSourcePayloadAsync(string appDir)
    {
        var assembly = Assembly.GetEntryAssembly()!;
        using var stream = assembly.GetManifestResourceStream("payload.tar.gz")
            ?? throw new InvalidOperationException("Embedded payload not found. Run build.py first.");

        using var gz = new GZipStream(stream, CompressionMode.Decompress);
        using var tarReader = new TarReader(gz);

        TarEntry? entry;
        while ((entry = tarReader.GetNextEntry()) != null)
        {
            if (string.IsNullOrEmpty(entry.Name))
                continue;

            if (entry.EntryType == TarEntryType.Directory)
            {
                Directory.CreateDirectory(Path.Combine(appDir, entry.Name));
                continue;
            }

            if (entry.EntryType == TarEntryType.RegularFile && entry.DataStream != null)
            {
                var filePath = Path.Combine(appDir, entry.Name);
                var dir = Path.GetDirectoryName(filePath);
                if (dir != null) Directory.CreateDirectory(dir);

                using var fs = new FileStream(filePath, FileMode.Create, FileAccess.Write, FileShare.None, 81920);
                await entry.DataStream.CopyToAsync(fs);
            }
        }
    }

    private static async Task ExtractUvBinaryAsync(string appDir)
    {
        var assembly = Assembly.GetEntryAssembly()!;
        using var stream = assembly.GetManifestResourceStream("uv.bin")
            ?? throw new InvalidOperationException("Embedded uv binary not found. Run build.py first.");

        var uvPath = GetUvBinaryPath(appDir);
        var dir = Path.GetDirectoryName(uvPath);
        if (dir != null) Directory.CreateDirectory(dir);

        using var fs = new FileStream(uvPath, FileMode.Create, FileAccess.Write, FileShare.None, 81920);
        await stream.CopyToAsync(fs);

        if (!IsWindows)
        {
            try
            {
                var chmod = Process.Start(new ProcessStartInfo
                {
                    FileName = "chmod",
                    Arguments = $"+x \"{uvPath}\"",
                    UseShellExecute = false,
                    CreateNoWindow = true
                });
                if (chmod != null) await chmod.WaitForExitAsync();
            }
            catch { }
        }
    }

    private static async Task<int> RunUvCommandAsync(
        string uvPath,
        string workingDir,
        string arguments,
        string appDir,
        Action<int>? onProgress = null,
        Action<string>? onStatus = null)
    {
        var psi = new ProcessStartInfo
        {
            FileName = uvPath,
            Arguments = arguments,
            WorkingDirectory = workingDir,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8
        };

        psi.EnvironmentVariables["UV_HOME"] = Path.Combine(appDir, "uv-home");
        psi.EnvironmentVariables["UV_PYTHON_INSTALL_DIR"] = Path.Combine(appDir, "python");
        psi.EnvironmentVariables["UV_CACHE_DIR"] = Path.Combine(appDir, "cache");
        psi.EnvironmentVariables["UV_PYTHON_PREFERENCE"] = "only-managed";

        if (IsWindows)
        {
            psi.EnvironmentVariables["UV_FORCE_ANSI"] = "1";
        }

        using var proc = new Process { StartInfo = psi, EnableRaisingEvents = true };
        var outputLines = new List<string>();
        var errorLines = new List<string>();

        proc.OutputDataReceived += (_, e) =>
        {
            if (e.Data == null) return;
            lock (_lock) outputLines.Add(e.Data);
            TryParseProgress(e.Data, onProgress);
            TryParsePackageStatus(e.Data, onStatus);
        };

        proc.ErrorDataReceived += (_, e) =>
        {
            if (e.Data == null) return;
            lock (_lock) errorLines.Add(e.Data);
            TryParseProgress(e.Data, onProgress);
            TryParsePackageStatus(e.Data, onStatus);
        };

        proc.Start();
        proc.BeginOutputReadLine();
        proc.BeginErrorReadLine();

        await proc.WaitForExitAsync();

        if (proc.ExitCode != 0 && onProgress == null)
        {
            lock (_lock)
            {
                if (errorLines.Count > 0)
                    throw new Exception($"uv failed (exit {proc.ExitCode}): {string.Join("\n", errorLines.Take(10))}");
            }
        }

        return proc.ExitCode;
    }

    private static readonly Regex PercentRegex = new(@"(\d{1,3})%", RegexOptions.Compiled);

    private static readonly Regex PackageDownloadRegex = new(
        @"(?:Downloading|Downloading\s+package|Fetch)\s+([\w\-\.]+)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    private static readonly Regex PackageInstallRegex = new(
        @"(?:Installing|Install|Installed)\s+([\w\-\.]+)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    private static readonly Regex PackageBuildRegex = new(
        @"(?:Building|Built|Build)\s+([\w\-\.]+)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    private static readonly Regex ResolvedRegex = new(
        @"Resolved\s+(\d+)\s+packages?",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    private static readonly Regex DownloadedRegex = new(
        @"(?:Downloaded|Downloading)\s+(\d+)\s+packages?",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    private static void TryParseProgress(string line, Action<int>? onProgress)
    {
        if (onProgress == null) return;

        var match = PercentRegex.Match(line);
        if (match.Success && int.TryParse(match.Groups[1].Value, out var pct))
        {
            onProgress(Math.Clamp(pct, 0, 100));
        }
    }

    private static void TryParsePackageStatus(string line, Action<string>? onStatus)
    {
        if (onStatus == null) return;

        var raw = line.TrimStart();
        if (string.IsNullOrWhiteSpace(raw)) return;

        var clean = Regex.Replace(raw, @"\x1b\[[0-9;]*[A-Za-z]", "");
        clean = clean.Trim();

        var resolvedMatch = ResolvedRegex.Match(clean);
        if (resolvedMatch.Success)
        {
            onStatus($"Resolved {resolvedMatch.Groups[1].Value} packages");
            return;
        }

        var downloadMatch = PackageDownloadRegex.Match(clean);
        if (downloadMatch.Success)
        {
            onStatus($"Downloading {downloadMatch.Groups[1].Value}");
            return;
        }

        var buildMatch = PackageBuildRegex.Match(clean);
        if (buildMatch.Success)
        {
            onStatus($"Building {buildMatch.Groups[1].Value}");
            return;
        }

        var installMatch = PackageInstallRegex.Match(clean);
        if (installMatch.Success)
        {
            onStatus($"Installing {installMatch.Groups[1].Value}");
            return;
        }
    }

    private static async Task<int> LaunchApplicationAsync(string venvPython, string mainPy, string appDir)
    {
        var psi = new ProcessStartInfo
        {
            FileName = venvPython,
            Arguments = $"\"{mainPy}\"",
            WorkingDirectory = appDir,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };

        if (IsWindows)
        {
            psi.EnvironmentVariables["PYTHONNOUSERSITE"] = "1";
        }

        using var proc = new Process { StartInfo = psi, EnableRaisingEvents = true };
        lock (_lock) _childProcess = proc;

        proc.Start();
        proc.BeginOutputReadLine();
        proc.BeginErrorReadLine();
        await proc.WaitForExitAsync();

        return proc.ExitCode;
    }

    private static bool IsCacheValid(string appDir)
    {
        try
        {
            var hashFile = Path.Combine(appDir, ".cache-hash");
            if (!File.Exists(hashFile)) return false;

            var reqFile = Path.Combine(appDir, "requirements.txt");
            if (!File.Exists(reqFile)) return false;

            var reqContents = File.ReadAllText(reqFile);
            var currentHash = ComputeHash(reqContents + "|" + AppVersion);
            var storedHash = File.ReadAllText(hashFile).Trim();

            return string.Equals(currentHash, storedHash, StringComparison.Ordinal);
        }
        catch
        {
            return false;
        }
    }

    private static void WriteCacheHash(string appDir)
    {
        try
        {
            var reqFile = Path.Combine(appDir, "requirements.txt");
            var hash = ComputeHash((File.Exists(reqFile) ? File.ReadAllText(reqFile) : "") + "|" + AppVersion);
            File.WriteAllText(Path.Combine(appDir, ".cache-hash"), hash);
        }
        catch { }
    }

    private static string ComputeHash(string input)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(input));
        return Convert.ToHexString(bytes);
    }

    private static int MapProgress(int subPercent, int rangeStart, int rangeEnd)
    {
        return rangeStart + (int)(subPercent / 100.0 * (rangeEnd - rangeStart));
    }

    private static int _depPackagesInstalled;
    private static readonly object _depLock = new();

    private static int EstimateDependencyProgress(string detail, string reqFile)
    {
        var totalPackages = CountRequirements(reqFile);
        if (totalPackages <= 0) totalPackages = 10;

        bool isInstall = detail.StartsWith("Installing ", StringComparison.OrdinalIgnoreCase)
                       || detail.StartsWith("Installed ", StringComparison.OrdinalIgnoreCase)
                       || detail.StartsWith("Downloading ", StringComparison.OrdinalIgnoreCase);

        if (isInstall)
        {
            lock (_depLock)
            {
                _depPackagesInstalled++;
                var pct = (int)((double)_depPackagesInstalled / (totalPackages + 2) * 100);
                return Math.Clamp(pct, 0, 100);
            }
        }

        lock (_depLock)
        {
            if (_depPackagesInstalled > 0)
            {
                var pct = (int)((double)_depPackagesInstalled / (totalPackages + 2) * 100);
                return Math.Clamp(pct, 0, 100);
            }
        }

        return 5;
    }

    private static int CountRequirements(string reqFile)
    {
        try
        {
            if (!File.Exists(reqFile)) return 0;
            var lines = File.ReadAllLines(reqFile);
            return lines.Count(l =>
            {
                var t = l.Trim();
                return !string.IsNullOrEmpty(t) && !t.StartsWith("#");
            });
        }
        catch { return 0; }
    }

    private static void Shutdown(int exitCode)
    {
        CleanupChildProcess();

        Dispatcher.UIThread.Post(() =>
        {
            if (Application.Current?.ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
            {
                desktop.Shutdown(exitCode);
            }
        });
    }

    private static void CleanupChildProcess()
    {
        lock (_lock)
        {
            if (_childProcess != null && !_childProcess.HasExited)
            {
                try { _childProcess.Kill(entireProcessTree: true); } catch { }
            }
            _childProcess = null;
        }
    }
}
