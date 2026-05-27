using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;

namespace PST.Bootstrapper;

public partial class App : Application
{
    public static SplashWindow? Splash { get; private set; }

    public override void Initialize()
    {
        AvaloniaXamlLoader.Load(this);
    }

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            var splash = new SplashWindow();
            Splash = splash;
            desktop.MainWindow = splash;
        }

        base.OnFrameworkInitializationCompleted();
    }
}
