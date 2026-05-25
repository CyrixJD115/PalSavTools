from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QCursor
try:
    import nerdfont as nf
except:
    class nf:
        icons = {'nf-cod-tools': '\uea83', 'nf-cod-globe': '\ueaf0', 'nf-cod-package': '\ueb3f', 'nf-cod-archive': '\ueb07', 'nf-cod-star-full': '\ueb7c', 'nf-cod-organization': '\ueb87', 'nf-cod-shield': '\ueb4b', 'nf-cod-home': '\ueaa2', 'nf-cod-circle-slash': '\uea54', 'nf-cod-triangle_right': '\ueb9c', 'nf-cod-triangle_left': '\ueb9b', 'nf-cod-terminal': '\ueac5'}
from i18n import t

ICONS = {
    'tools': nf.icons.get('nf-cod-tools', '\uea83'),
    'map': nf.icons.get('nf-cod-globe', '\ueaf0'),
    'base_inventory': nf.icons.get('nf-cod-package', '\ueb3f'),
    'player_inventory': nf.icons.get('nf-cod-archive', '\ueb07'),
    'pal_editor': nf.icons.get('nf-cod-star-full', '\ueb7c'),
    'players': nf.icons.get('nf-cod-organization', '\ueb87'),
    'guilds': nf.icons.get('nf-cod-shield', '\ueb4b'),
    'bases': nf.icons.get('nf-cod-home', '\ueaa2'),
    'exclusions': nf.icons.get('nf-cod-circle-slash', '\uea54'),
    'collapse_open': nf.icons.get('nf-cod-triangle_right', '\ueb9c'),
    'collapse_close': nf.icons.get('nf-cod-triangle_left', '\ueb9b'),
    'console': nf.icons.get('nf-cod-terminal', '\ueac5'),
}

SIDEBAR_W = 48
ITEM_H = 44

class NavItem(QPushButton):
    clicked_with_id = Signal(str)
    def __init__(self, button_id, icon_code, label, parent=None):
        super().__init__(parent)
        self._id = button_id
        self.setProperty('sidebarItem', True)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFont(QFont('Hack Nerd Font', 18))
        self.setFixedSize(SIDEBAR_W, ITEM_H)
        self.setText(icon_code)
        self.setToolTip(label)
        self.clicked.connect(lambda: self.clicked_with_id.emit(self._id))
    def set_active(self, active):
        self.setProperty('active', active)
        self.style().unpolish(self)
        self.style().polish(self)

class BottomBtn(QPushButton):
    def __init__(self, icon_code, tooltip, parent=None):
        super().__init__(parent)
        self.setProperty('sidebarItem', True)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFont(QFont('Hack Nerd Font', 16))
        self.setFixedSize(SIDEBAR_W, ITEM_H)
        self.setText(icon_code)
        self.setToolTip(tooltip)
    def set_icon(self, icon_code):
        self.setText(icon_code)

class SidebarWidget(QWidget):
    nav_changed = Signal(str)
    console_toggled = Signal()
    right_panel_toggled = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('sideBar')
        self.setFixedWidth(SIDEBAR_W)
        self._buttons = {}
        self._active_id = None
        self._right_panel_visible = True
        self._setup_ui()
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(2)
        nav_items = [
            ('tools', ICONS['tools'], t('tools_tab') if t else 'Tools'),
            ('map', ICONS['map'], t('map.viewer') if t else 'Map'),
            ('base_inventory', ICONS['base_inventory'], t('base_inventory.tab') if t else 'Base Inventory'),
            ('player_inventory', ICONS['player_inventory'], t('inventory.tab') if t else 'Player Inventory'),
            ('pal_editor', ICONS['pal_editor'], t('pal_editor.tab') if t else 'Pal Editor'),
            ('players', ICONS['players'], t('deletion.search_players') if t else 'Players'),
            ('guilds', ICONS['guilds'], t('deletion.search_guilds') if t else 'Guilds'),
            ('bases', ICONS['bases'], t('deletion.search_bases') if t else 'Bases'),
            ('exclusions', ICONS['exclusions'], t('deletion.menu.exclusions') if t else 'Exclusions'),
        ]
        for btn_id, icon, label in nav_items:
            item = NavItem(btn_id, icon, label)
            item.clicked_with_id.connect(self._on_item_clicked)
            self._buttons[btn_id] = item
            layout.addWidget(item)
        layout.addStretch()
        self._console_btn = BottomBtn(ICONS['console'], t('console.detach') if t else 'Console')
        self._console_btn.clicked.connect(self.console_toggled.emit)
        layout.addWidget(self._console_btn)
        self._right_panel_btn = BottomBtn(ICONS['collapse_close'], t('sidebar.close') if t else 'Close Panel')
        self._right_panel_btn.clicked.connect(self._on_right_panel_toggle)
        layout.addWidget(self._right_panel_btn)
    def _on_item_clicked(self, button_id):
        self.set_active(button_id)
        self.nav_changed.emit(button_id)
    def set_active(self, button_id):
        if button_id not in self._buttons:
            return
        self._active_id = button_id
        for bid, btn in self._buttons.items():
            btn.set_active(bid == button_id)
    def _on_right_panel_toggle(self):
        self._right_panel_visible = not self._right_panel_visible
        self._update_right_panel_icon()
        self.right_panel_toggled.emit()
    def set_right_panel_visible(self, visible):
        self._right_panel_visible = visible
        self._update_right_panel_icon()
    def _update_right_panel_icon(self):
        if self._right_panel_visible:
            self._right_panel_btn.set_icon(ICONS['collapse_close'])
            self._right_panel_btn.setToolTip(t('sidebar.close') if t else 'Close Panel')
        else:
            self._right_panel_btn.set_icon(ICONS['collapse_open'])
            self._right_panel_btn.setToolTip(t('sidebar.open') if t else 'Open Panel')
    def refresh_labels(self):
        pass
