using Avalonia;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using Avalonia.Platform;
using Avalonia.Threading;

namespace PST.Bootstrapper;

public partial class SplashWindow : Window
{
    private ProgressBar? _progress;
    private TextBlock? _statusText;
    private TextBlock? _percentText;
    private TextBlock? _detailText;
    private const double CornerRadiusValue = 16;

    public SplashWindow()
    {
        InitializeComponent();
        LoadAssets();
    }

    private void LoadAssets()
    {
        try
        {
            var bg = this.FindControl<Image>("BackgroundImage");
            if (bg != null)
            {
                using var bgStream = AssetLoader.Open(new Uri("avares://PST.Bootstrapper/assets/background.png"));
                bg.Source = new Bitmap(bgStream);
            }
        }
        catch { }

        try
        {
            var logo = this.FindControl<Image>("LogoImage");
            if (logo != null)
            {
                using var logoStream = AssetLoader.Open(new Uri("avares://PST.Bootstrapper/assets/logo.png"));
                logo.Source = new Bitmap(logoStream);
            }
        }
        catch { }
    }

    protected override void OnLoaded(RoutedEventArgs e)
    {
        base.OnLoaded(e);
        _progress = this.FindControl<ProgressBar>("SplashProgress");
        _statusText = this.FindControl<TextBlock>("StatusText");
        _percentText = this.FindControl<TextBlock>("PercentText");
        _detailText = this.FindControl<TextBlock>("DetailText");

        ApplyRoundedClip();
    }

    protected override void OnResized(WindowResizedEventArgs e)
    {
        base.OnResized(e);
        ApplyRoundedClip();
    }

    private void ApplyRoundedClip()
    {
        var r = CornerRadiusValue;
        var w = Bounds.Width;
        var h = Bounds.Height;
        if (w <= 0 || h <= 0) return;

        var geometry = new StreamGeometry();
        using (var ctx = geometry.Open())
        {
            var rect = new Rect(0, 0, w, h);
            ctx.BeginFigure(new Point(rect.Left + r, rect.Top), true);
            ctx.LineTo(new Point(rect.Right - r, rect.Top));
            ctx.ArcTo(new Point(rect.Right, rect.Top + r), new Size(r, r), 0, false, SweepDirection.Clockwise);
            ctx.LineTo(new Point(rect.Right, rect.Bottom - r));
            ctx.ArcTo(new Point(rect.Right - r, rect.Bottom), new Size(r, r), 0, false, SweepDirection.Clockwise);
            ctx.LineTo(new Point(rect.Left + r, rect.Bottom));
            ctx.ArcTo(new Point(rect.Left, rect.Bottom - r), new Size(r, r), 0, false, SweepDirection.Clockwise);
            ctx.LineTo(new Point(rect.Left, rect.Top + r));
            ctx.ArcTo(new Point(rect.Left + r, rect.Top), new Size(r, r), 0, false, SweepDirection.Clockwise);
            ctx.EndFigure(true);
        }
        Clip = geometry;
    }

    public void UpdateProgress(int percent, string status, string? detail = null)
    {
        Dispatcher.UIThread.Post(() =>
        {
            if (_progress != null)
                _progress.Value = Math.Clamp(percent, 0, 100);

            if (_statusText != null)
                _statusText.Text = status;

            if (_percentText != null)
                _percentText.Text = $"{Math.Clamp(percent, 0, 100)}%";

            if (_detailText != null)
                _detailText.Text = detail ?? "";
        });
    }

    public void CloseSplash()
    {
        try
        {
            Dispatcher.UIThread.Post(() =>
            {
                try { Close(); } catch { }
            });
        }
        catch { }
    }
}
