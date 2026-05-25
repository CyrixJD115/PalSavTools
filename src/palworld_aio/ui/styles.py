DIALOG_STYLE = '''
QDialog {
    background: qlineargradient(spread:pad, x1:0.0, y1:0.0, x2:1.0, y2:1.0,
                stop:0 rgba(12,14,18,0.98), stop:0.5 rgba(10,16,22,0.98), stop:1 rgba(8,12,18,0.98));
    color: #e2e8f0;
}
QLabel {
    color: #e2e8f0;
}
QLineEdit {
    background: rgba(255,255,255,0.06);
    color: #e2e8f0;
    border: 1px solid rgba(125,211,252,0.2);
    border-radius: 6px;
    padding: 6px 10px;
}
QLineEdit:focus {
    border-color: rgba(125,211,252,0.4);
}
QSpinBox {
    background: rgba(255,255,255,0.06);
    color: #e2e8f0;
    border: 1px solid rgba(125,211,252,0.2);
    border-radius: 6px;
    padding: 4px 8px;
}
QSpinBox:focus {
    border-color: rgba(125,211,252,0.4);
}
QComboBox {
    background: rgba(255,255,255,0.06);
    color: #e2e8f0;
    border: 1px solid rgba(125,211,252,0.2);
    border-radius: 6px;
    padding: 6px 10px;
}
QComboBox:hover {
    border-color: rgba(125,211,252,0.3);
}
QComboBox QAbstractItemView {
    background-color: rgba(18,20,24,0.98);
    color: #e2e8f0;
    border: 1px solid rgba(125,211,252,0.2);
    selection-background-color: rgba(59,142,208,0.3);
    border-radius: 4px;
}
QPushButton {
    background: rgba(125,211,252,0.12);
    color: #7DD3FC;
    border: 1px solid rgba(125,211,252,0.2);
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background: rgba(125,211,252,0.2);
    border-color: rgba(125,211,252,0.4);
    color: #FFFFFF;
}
QPushButton:pressed {
    background: rgba(125,211,252,0.3);
}
QListWidget {
    background: rgba(255,255,255,0.03);
    color: #e2e8f0;
    border: 1px solid rgba(125,211,252,0.15);
    border-radius: 6px;
}
QListWidget::item {
    padding: 4px;
    border: 1px solid rgba(125,211,252,0.12);
    border-radius: 4px;
    margin: 2px;
}
QListWidget::item:hover {
    border: 1px solid rgba(125,211,252,0.3);
    background: rgba(125,211,252,0.05);
}
QListWidget::item:selected {
    background: rgba(59,142,208,0.3);
    border: 1px solid rgba(59,142,208,0.5);
}
QGroupBox {
    color: #e2e8f0;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QCheckBox {
    color: #e2e8f0;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
QTabWidget::pane {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(125,211,252,0.15);
    border-radius: 6px;
}
QTabBar::tab {
    background: rgba(255,255,255,0.06);
    color: #e2e8f0;
    padding: 6px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background: rgba(125,211,252,0.12);
    color: #7DD3FC;
}
QTabBar::tab:hover {
    background: rgba(255,255,255,0.1);
}
QRadioButton {
    color: #e2e8f0;
}
QTextEdit {
    background: rgba(255,255,255,0.05);
    color: #e2e8f0;
    border: 1px solid rgba(125,211,252,0.15);
    border-radius: 6px;
}
'''

MENU_STYLE = '''
QMenu {
    background: qlineargradient(spread:pad, x1:0.0, y1:0.0, x2:1.0, y2:1.0,
                stop:0 rgba(10,12,16,0.98), stop:0.5 rgba(12,16,22,0.98), stop:1 rgba(8,10,14,0.98));
    border: 1px solid rgba(125,211,252,0.2);
    border-radius: 6px;
    color: #e2e8f0;
    padding: 4px;
}
QMenu::item {
    padding: 6px 16px;
    border-radius: 3px;
    color: #e2e8f0;
}
QMenu::item:selected {
    background: rgba(125,211,252,0.15);
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: rgba(255,255,255,0.1);
    margin: 4px 8px;
}
'''

STATS_PANEL_STYLE = '''
StatsPanelWidget {
    background: rgba(18,20,24,0.95);
    border: 1px solid rgba(125,211,252,0.2);
    border-radius: 8px;
}
StatsPanelWidget QLabel {
    color: #e2e8f0;
}
StatsPanelWidget QLineEdit {
    background: rgba(255,255,255,0.06);
    color: #e2e8f0;
    border: 1px solid rgba(125,211,252,0.2);
    border-radius: 4px;
    padding: 2px 4px;
}
StatsPanelWidget QLineEdit:focus {
    border-color: rgba(125,211,252,0.4);
}
StatsPanelWidget QPushButton {
    background: rgba(125,211,252,0.1);
    color: #7DD3FC;
    border: 1px solid rgba(125,211,252,0.2);
    border-radius: 3px;
    font-weight: bold;
}
StatsPanelWidget QPushButton:hover {
    background: rgba(125,211,252,0.2);
}
StatsPanelWidget QProgressBar {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(125,211,252,0.15);
    border-radius: 3px;
}
StatsPanelWidget QProgressBar::chunk {
    background: rgba(34,197,94,0.6);
    border-radius: 2px;
}
'''

PICKER_BG_STYLE = 'QWidget { background: rgba(18,20,24,0.98); border: 1px solid rgba(125,211,252,0.2); border-radius: 8px; }'

PICKER_SEARCH_STYLE = 'QLineEdit { background: rgba(255,255,255,0.06); color: #e2e8f0; border: 1px solid rgba(125,211,252,0.2); border-radius: 4px; padding: 4px 8px; font-size: 12px; }'

PICKER_LIST_STYLE = 'QListWidget { background: transparent; color: #e2e8f0; border: none; font-size: 12px; } QListWidget::item { padding: 3px 8px; border-radius: 3px; } QListWidget::item:hover { background: rgba(59,142,208,0.2); } QListWidget::item:selected { background: rgba(59,142,208,0.35); }'

INPUT_DIALOG_STYLE = 'QInputDialog{background:rgba(18,20,24,0.98);color:#e2e8f0}QLabel{color:#e2e8f0}QLineEdit{background:rgba(255,255,255,0.06);color:#e2e8f0;border:1px solid rgba(125,211,252,0.2);border-radius:4px;padding:4px 8px}QSpinBox{background:rgba(255,255,255,0.06);color:#e2e8f0;border:1px solid rgba(125,211,252,0.2);border-radius:4px;padding:4px}QPushButton{background:rgba(125,211,252,0.12);color:#7DD3FC;border:1px solid rgba(125,211,252,0.2);border-radius:4px;padding:4px 12px}QPushButton:hover{background:rgba(125,211,252,0.2)}'

TOOLTIP_STYLE = '\nQToolTip { background: rgba(18,20,24,0.98); color: #E2E8F0; border: 1px solid rgba(125,211,252,0.25); border-radius: 6px; padding: 6px 10px; font-size: 11px; }'
