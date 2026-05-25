from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea
from PySide6.QtCore import Signal, Qt, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QFont, QCursor
try:
    import nerdfont as nf
except:
    class nf:
        icons = {'nf-cod-triangle_left': '\ueb9b', 'nf-cod-triangle_right': '\ueb9c', 'nf-cod-tools': '\uea83', 'nf-cod-globe': '\ueaf0', 'nf-cod-package': '\ueb3f', 'nf-cod-archive': '\ueb07', 'nf-cod-star-full': '\ueb7c', 'nf-cod-organization': '\ueb87', 'nf-cod-shield': '\ueb4b', 'nf-cod-home': '\ueaa2', 'nf-cod-circle-slash': '\uea54', 'nf-cod-rocket': '\uebb5'}
from i18n import t
from palworld_aio import constants

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
    'brand': nf.icons.get('nf-cod-rocket', '\uebb5'),
}

class SidebarButton(QWidget):
    clicked_with_id = Signal(str)
    def __init__(self, button_id, icon_code, label_text, parent=None):
        super().__init__(parent)
        self._id = button_id
        self._icon = icon_code
        self._label = label_text
        self._active = False
        self._expanded = True
        self._hovered = False
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(42)
        self.setProperty('navButton', True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._active_bar = QWidget()
        self._active_bar.setFixedWidth(3)
        self._active_bar.setObjectName('navActiveBar')
        layout.addWidget(self._active_bar)
        self._icon_label = QLabel(self._icon)
        self._icon_label.setFont(QFont('Hack Nerd Font', 18))
        self._icon_label.setFixedWidth(44)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setObjectName('navIcon')
        layout.addWidget(self._icon_label)
        self._text_label = QLabel(self._label)
        self._text_label.setFont(QFont(constants.FONT_FAMILY, 11, QFont.DemiBold))
        self._text_label.setObjectName('navText')
        layout.addWidget(self._text_label)
        layout.addStretch()
        self._update_style()
    def _update_style(self):
        if self._active:
            self._active_bar.setStyleSheet('background: #7DD3FC; border-radius: 2px;')
            self._icon_label.setStyleSheet('color: #7DD3FC;')
            self._text_label.setStyleSheet('color: #7DD3FC; font-weight: 700;')
        elif self._hovered:
            self._active_bar.setStyleSheet('background: transparent;')
            self._icon_label.setStyleSheet('color: #E6EEF6;')
            self._text_label.setStyleSheet('color: #E6EEF6;')
        else:
            self._active_bar.setStyleSheet('background: transparent;')
            self._icon_label.setStyleSheet('color: #A6B8C8;')
            self._text_label.setStyleSheet('color: #A6B8C8;')
    def set_active(self, active):
        self._active = active
        self._update_style()
    def set_expanded(self, expanded):
        self._expanded = expanded
        self._text_label.setVisible(expanded)
        if not expanded:
            self.setToolTip(self._label)
        else:
            self.setToolTip('')
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked_with_id.emit(self._id)
    def enterEvent(self, event):
        self._hovered = True
        self._update_style()
    def leaveEvent(self, event):
        self._hovered = False
        self._update_style()

class NavGroup(QWidget):
    def __init__(self, header_text, parent=None):
        super().__init__(parent)
        self._buttons = []
        self.setProperty('navGroup', True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._header = QLabel(header_text.upper() if header_text else '')
        self._header.setObjectName('navGroupHeader')
        self._header.setFont(QFont(constants.FONT_FAMILY, 9, QFont.Bold))
        layout.addWidget(self._header)
        self._buttons_layout = QVBoxLayout()
        self._buttons_layout.setContentsMargins(0, 2, 0, 8)
        self._buttons_layout.setSpacing(2)
        layout.addLayout(self._buttons_layout)
    def add_button(self, button):
        self._buttons.append(button)
        self._buttons_layout.addWidget(button)
    def set_expanded(self, expanded):
        self._header.setVisible(expanded)

class SidebarWidget(QWidget):
    nav_changed = Signal(str)
    collapsed_changed = Signal(bool)
    EXPANDED_WIDTH = 200
    COLLAPSED_WIDTH = 56
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('sideBar')
        self._expanded = True
        self._buttons = {}
        self._groups = []
        self._animation = QVariantAnimation()
        self._animation.setDuration(280)
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._animation.valueChanged.connect(self.setFixedWidth)
        self._animation.finished.connect(self._on_animation_finished)
        self._setup_ui()
        self.setFixedWidth(self.EXPANDED_WIDTH)
    def _setup_ui(self):
        self.setMinimumWidth(self.COLLAPSED_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._brand_frame = QWidget()
        self._brand_frame.setObjectName('sidebarBrand')
        self._brand_frame.setFixedHeight(52)
        brand_layout = QHBoxLayout(self._brand_frame)
        brand_layout.setContentsMargins(14, 0, 12, 0)
        brand_layout.setSpacing(8)
        self._brand_icon = QLabel(ICONS['brand'])
        self._brand_icon.setFont(QFont('Hack Nerd Font', 20))
        self._brand_icon.setFixedWidth(28)
        self._brand_icon.setAlignment(Qt.AlignCenter)
        brand_layout.addWidget(self._brand_icon)
        self._brand_label = QLabel('PST')
        self._brand_label.setToolTip('Palworld Save Tools')
        self._brand_label.setFont(QFont(constants.FONT_FAMILY, 14, QFont.Bold))
        brand_layout.addWidget(self._brand_label)
        brand_layout.addStretch()
        layout.addWidget(self._brand_frame)
        self._nav_scroll = QScrollArea()
        self._nav_scroll.setObjectName('sidebarScroll')
        self._nav_scroll.setWidgetResizable(True)
        self._nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._nav_scroll.setFrameShape(QScrollArea.NoFrame)
        scroll_content = QWidget()
        scroll_content.setObjectName('sidebarScrollContent')
        self._nav_layout = QVBoxLayout(scroll_content)
        self._nav_layout.setContentsMargins(0, 10, 0, 10)
        self._nav_layout.setSpacing(4)
        self._add_nav_items()
        self._nav_layout.addStretch()
        self._nav_scroll.setWidget(scroll_content)
        layout.addWidget(self._nav_scroll, stretch=1)
        self._bottom_frame = QWidget()
        self._bottom_frame.setObjectName('sidebarBottom')
        self._bottom_frame.setFixedHeight(56)
        bottom_layout = QVBoxLayout(self._bottom_frame)
        bottom_layout.setContentsMargins(12, 8, 12, 8)
        bottom_layout.setSpacing(0)
        self._collapse_btn = QPushButton()
        self._collapse_btn.setObjectName('sidebarCollapseBtn')
        self._collapse_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._collapse_btn.setFont(QFont('Hack Nerd Font', 13))
        self._collapse_btn.setFixedHeight(36)
        self._collapse_btn.clicked.connect(self.toggle_collapsed)
        bottom_layout.addWidget(self._collapse_btn)
        self._version_label = QLabel()
        self._version_label.setObjectName('sidebarVersion')
        self._version_label.setFont(QFont(constants.FONT_FAMILY, 8))
        self._version_label.setAlignment(Qt.AlignCenter)
        bottom_layout.addWidget(self._version_label)
        layout.addWidget(self._bottom_frame)
        self._update_collapse_button()
    def _add_nav_items(self):
        nav_items = [
            ('MANAGEMENT', [
                ('tools', ICONS['tools'], t('tools_tab') if t else 'Tools'),
                ('map', ICONS['map'], t('map.viewer') if t else 'Map'),
            ]),
            ('INVENTORIES', [
                ('base_inventory', ICONS['base_inventory'], t('base_inventory.tab') if t else 'Base Inventory'),
                ('player_inventory', ICONS['player_inventory'], t('inventory.tab') if t else 'Player Inventory'),
            ]),
            ('EDITOR', [
                ('pal_editor', ICONS['pal_editor'], t('pal_editor.tab') if t else 'Pal Editor'),
            ]),
            ('SEARCH', [
                ('players', ICONS['players'], t('deletion.search_players') if t else 'Players'),
                ('guilds', ICONS['guilds'], t('deletion.search_guilds') if t else 'Guilds'),
                ('bases', ICONS['bases'], t('deletion.search_bases') if t else 'Bases'),
            ]),
            ('SYSTEM', [
                ('exclusions', ICONS['exclusions'], t('deletion.menu.exclusions') if t else 'Exclusions'),
            ]),
        ]
        for group_header, items in nav_items:
            group = NavGroup(group_header if t else group_header)
            for btn_id, icon, label in items:
                btn = SidebarButton(btn_id, icon, label)
                btn.clicked_with_id.connect(self._on_button_clicked)
                self._buttons[btn_id] = btn
                group.add_button(btn)
            self._groups.append(group)
            self._nav_layout.addWidget(group)
    def set_version(self, version_text):
        self._version_label.setText(version_text)
    def _on_button_clicked(self, button_id):
        for btn_id, btn in self._buttons.items():
            btn.set_active(btn_id == button_id)
        self.nav_changed.emit(button_id)
    def set_active(self, button_id):
        if button_id in self._buttons:
            for btn_id, btn in self._buttons.items():
                btn.set_active(btn_id == button_id)
    def toggle_collapsed(self):
        self.set_expanded(not self._expanded)
    def set_expanded(self, expanded):
        if self._expanded == expanded:
            return
        self._expanded = expanded
        if not self._expanded:
            for group in self._groups:
                group.set_expanded(False)
            for btn in self._buttons.values():
                btn.set_expanded(False)
            self._brand_label.setVisible(False)
            self._version_label.setVisible(False)
        self._animation.stop()
        start_w = self.COLLAPSED_WIDTH if self._expanded else self.EXPANDED_WIDTH
        end_w = self.EXPANDED_WIDTH if self._expanded else self.COLLAPSED_WIDTH
        self._animation.setStartValue(start_w)
        self._animation.setEndValue(end_w)
        self._animation.start()
        self._update_collapse_button()
        self.collapsed_changed.emit(expanded)
    def _on_animation_finished(self):
        if self._expanded:
            for group in self._groups:
                group.set_expanded(True)
            for btn in self._buttons.values():
                btn.set_expanded(True)
            self._brand_label.setVisible(True)
            self._version_label.setVisible(True)
    def _update_collapse_button(self):
        icon = nf.icons.get('nf-cod-triangle_left', '\ueb9b')
        label = t('sidebar.close') if t else 'Collapse'
        if not self._expanded:
            icon = nf.icons.get('nf-cod-triangle_right', '\ueb9c')
            label = t('sidebar.open') if t else 'Expand'
        self._collapse_btn.setText(f'{icon}  {label}')
        self._collapse_btn.setToolTip(label)
    def refresh_labels(self):
        self._update_collapse_button()
