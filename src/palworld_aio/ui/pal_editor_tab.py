from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from i18n import t
from palworld_aio.edit_pals import PalEditorWidget
from palworld_aio.ui.styled_combo import StyledCombo
from palworld_aio import constants
class PalEditorTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_player_uid = None
        self.current_player_name = None
        self._player_list = []
        self._setup_ui()
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        header = QHBoxLayout()
        self.title_label = QLabel(t('pal_editor.title'))
        self.title_label.setFont(QFont(constants.FONT_FAMILY, constants.FONT_SIZE, QFont.Bold))
        self.title_label.setObjectName('sectionHeader')
        header.addWidget(self.title_label)
        header.addStretch()
        player_selector_layout = QHBoxLayout()
        player_selector_layout.setContentsMargins(0, 0, 0, 0)
        player_selector_layout.setSpacing(0)
        self.player_combo = StyledCombo()
        self.player_combo.setSearchable(True)
        self.player_combo.setSearchPlaceholder(t('inventory.search_players', default='Search players...'))
        self.player_combo.setFixedWidth(300)
        self.player_combo.currentIndexChanged.connect(self._on_player_selected)
        player_selector_layout.addWidget(self.player_combo)
        header.addLayout(player_selector_layout)
        main_layout.addLayout(header)
        self.content_area = self._create_content_area()
        main_layout.addWidget(self.content_area)
    def _create_content_area(self):
        frame = QFrame()
        frame.setObjectName('palEditorContent')
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        frame.setStyleSheet('\n            QFrame#palEditorContent {\n                background-color: rgba(20, 20, 30, 200);\n                border: 1px solid rgba(125, 211, 252, 0.2);\n                border-radius: 8px;\n            }\n        ')
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)
        self.placeholder_label = QLabel(t('pal_editor.select_player_hint', default='Select a player to edit their pals'))
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setMinimumHeight(400)
        self.placeholder_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.placeholder_label.setStyleSheet('\n            QLabel {\n                color: #888;\n                font-size: 14px;\n                background: transparent;\n            }\n        ')
        layout.addWidget(self.placeholder_label)
        self.pal_editor_widget = PalEditorWidget()
        self.pal_editor_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.pal_editor_widget.hide()
        layout.addWidget(self.pal_editor_widget)
        return frame
    def _on_player_selected(self, index):
        if index <= 0:
            self.current_player_uid = None
            self.current_player_name = None
            self._clear_editor()
            return
        uid = self.player_combo.currentData()
        if uid:
            self.current_player_uid = uid
            self.current_player_name = self.player_combo.currentText()
            self._show_editor()
    def _show_editor(self):
        if self.current_player_uid:
            self.placeholder_label.hide()
            self.pal_editor_widget.show()
            self.pal_editor_widget.set_player(self.current_player_uid, self.current_player_name)
    def _clear_editor(self):
        self.pal_editor_widget.hide()
        self.pal_editor_widget.clear()
        self.placeholder_label.show()
    def refresh(self):
        self._load_players()
    def _load_players(self):
        self._player_list = []
        self._clear_editor()
        self.player_combo.blockSignals(True)
        self.player_combo.clear()
        self.player_combo.addItem(t('inventory.select_player', default='Select Player...'), None)
        if constants.loaded_level_json:
            from palworld_aio.save_manager import save_manager
            players = save_manager.get_players()
            for uid, name, gid, lastseen, level in players:
                display_name = f'{name} (Lv.{level})'
                self.player_combo.addItem(display_name, uid)
                self._player_list.append({'uid': uid, 'name': name, 'level': level, 'display': display_name})
        self.player_combo.blockSignals(False)
        self.current_player_uid = None
        self.current_player_name = None
    def refresh_labels(self):
        if hasattr(self, 'title_label'):
            self.title_label.setText(t('pal_editor.title'))
        if hasattr(self, 'player_combo'):
            self.player_combo.setSearchPlaceholder(t('inventory.search_players', default='Search players...'))
        if hasattr(self, 'placeholder_label'):
            self.placeholder_label.setText(t('pal_editor.select_player_hint', default='Select a player to edit their pals'))
        if hasattr(self, 'pal_editor_widget'):
            self.pal_editor_widget.refresh_labels()