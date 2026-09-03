# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""主题中枢：深/浅双调色板、动态 SiColors 代理、全局 QSS 生成。

视觉语言：深黑底立体卡片 + 米家青绿主题色。主题色（THEME 系列）
与绿底上的文字在两种主题下完全一致；其余语义色按当前调色板取值。

用法约定：
- 界面代码一律 `from app.ui.si_theme import SiColors` 后取
  `SiColors.CARD` 等语义色——SiColors 经元类动态代理当前调色板，
  主题切换后新构建的控件自动取到新值；
- 内联样式是构造时求值的 f-string，已显示的界面在切换主题后由
  调用方重建（卡片网格/托盘行/工作台均为可重建结构）；
- 全局 QSS 由 build_qss() 生成，切换时整块替换。
"""

from string import Template
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLineEdit, QSizePolicy

from app.siui.components.button import SiSwitchRefactor, SiToggleButtonRefactor

if TYPE_CHECKING:
    from PySide6.QtWidgets import QComboBox

    from app.siui.components.label import SiLabelRefactor

# ----------------------------------------------------------------------------
# 强调色（主题色）多配色：深/浅两种明暗模式下可各选一套强调色，
# 主按钮/开关/选中态/链接/滚动条悬停等强调元素随它一起变
# ----------------------------------------------------------------------------
_ACCENT_DEFAULT = "green"
_ACCENT_KEYS = ("THEME", "THEME_HOVER", "THEME_DIM",
                "THEME_CHECKED_HOVER", "ON_THEME_TEXT")
ACCENTS: dict[str, dict[str, str]] = {
    "green": dict(THEME="#3dbba4", THEME_HOVER="#5fd0ba",
                  THEME_DIM="#2a8a7a", THEME_CHECKED_HOVER="#4ccdb5",
                  ON_THEME_TEXT="#0b0b0e"),
    "blue": dict(THEME="#4a8fe0", THEME_HOVER="#6ca7e8",
                 THEME_DIM="#356cb3", THEME_CHECKED_HOVER="#5a9ce6",
                 ON_THEME_TEXT="#ffffff"),
    "violet": dict(THEME="#8b78e0", THEME_HOVER="#a695ea",
                   THEME_DIM="#6a5cb8", THEME_CHECKED_HOVER="#9888e8",
                   ON_THEME_TEXT="#ffffff"),
    "orange": dict(THEME="#e8842f", THEME_HOVER="#f09c52",
                   THEME_DIM="#b9671f", THEME_CHECKED_HOVER="#ed913d",
                   ON_THEME_TEXT="#ffffff"),
    "rose": dict(THEME="#e25a86", THEME_HOVER="#ea7aa0",
                 THEME_DIM="#b24568", THEME_CHECKED_HOVER="#e56890",
                 ON_THEME_TEXT="#ffffff"),
    "cyan": dict(THEME="#1fa8b4", THEME_HOVER="#4bbcc6",
                 THEME_DIM="#17848e", THEME_CHECKED_HOVER="#36b3bd",
                 ON_THEME_TEXT="#0b0b0e"),
}
# 设置页下拉的顺序与文案
_ACCENT_LABELS = [
    ("green", "青绿（默认）"), ("blue", "海蓝"), ("violet", "黛紫"),
    ("orange", "琥珀橙"), ("rose", "玫瑰红"), ("cyan", "天青"),
]

SWITCH_THUMB = "#1C191F"       # 开关滑块深色拇指
DANGER = "#c0392b"             # 危险红（关闭按钮 hover 等）
DANGER_TEXT = "#e57373"
WHITE = "#ffffff"

_accent: str = _ACCENT_DEFAULT


def accent_options() -> list[tuple[str, str]]:
    """可用强调色选项：(key, 显示名)，用于设置页下拉。"""
    return list(_ACCENT_LABELS)


def current_accent() -> str:
    return _accent


def set_accent(key: str) -> None:
    """切换强调色（仅改取色；全局刷新由 theme_service 编排）。"""
    global _accent
    if key not in ACCENTS:
        raise ValueError(f"未知强调色: {key}")
    _accent = key


def _accent_color(name: str) -> str:
    return ACCENTS[_accent][name]

# ----------------------------------------------------------------------------
# 深/浅调色板：语义键 -> 色值。新增颜色一律进这里，不要在界面代码写死
# ----------------------------------------------------------------------------
PALETTES: dict[str, dict[str, str]] = {
    # 米家浅色风：灰画布 + 白卡片（对齐小米设计语言 miloco token）
    "light": dict(
        WINDOW_BG="#F4F5F7",
        TITLE_BAR_BG="#FFFFFF",
        TITLE_BAR_BORDER="#E5E5E5",
        CARD="#FFFFFF",
        CARD_HOVER="#F7F8FA",
        CARD_BORDER_HOVER="#D8DBE0",
        SURFACE="#F0F1F3",           # 输入框/小按钮/Toast 底
        SURFACE_PRESSED="#E6E8EB",   # 电源钮忙碌底
        PRESSED="#E2E4E7",           # 按下态
        BTN_PRESSED="#E2E4E7",       # 次级按钮按下
        BTN_HOVER="#EDEEF1",
        LINE="#E5E5E5",
        SCROLLBAR="#D5D7DB",
        SCROLLBAR_HOVER="#B8BCC3",
        TEXT_PRIMARY="#1F1F1F",
        TEXT_SECONDARY="#6B6B6B",
        TEXT_MUTED="#9A9A9A",
        TEXT_SUBTLE="#7A7A7A",
        TEXT_DISABLED="#C5C5C5",
        TEXT_FAINT="#D3D5D9",
        OFFLINE_CARD="#EBECEE",
        OFFLINE_TEXT="#9A9CA2",
        OFFLINE_SUB="#B4B6BB",
        ICON_DIM="#8F9399",
        ICON_MUTED="#B5B8BE",
        HOME_HOVER="#4A4C52",
        HOME_PRESSED="#70737A",
        THUMB="#8F9399",              # 滑块拇指：浅色模式中深灰（白底清晰）
        STATE_OFF="#D4D7DC",
        STATE_UNKNOWN_BG="#EEF0F2",
        STATE_UNKNOWN_BORDER="#CFD2D8",
        STATE_UNKNOWN_HOVER="#E4E6EA",
        ERROR_TEXT="#D93026",
        DEL_TEXT="#B05050",
        DEL_BORDER="#EBD6D6",
        DEL_BORDER_HOVER="#E0A8A8",
        WARN_BG="#FDF4E3",
        WARN_BORDER="#EFD8A8",
        WARN_TEXT="#8A6420",
    ),
    # 米家深色风：近黑画布 + 低饱和卡片（对齐 miloco dark token）
    "dark": dict(
        WINDOW_BG="#0E0E0E",
        TITLE_BAR_BG="#0E0E0E",
        TITLE_BAR_BORDER="#2A2A2A",
        CARD="#161616",
        CARD_HOVER="#1F1F1F",
        CARD_BORDER_HOVER="#383838",
        SURFACE="#1F1F1F",           # 输入框/小按钮/Toast 底
        SURFACE_PRESSED="#191919",   # 电源钮忙碌底
        PRESSED="#131313",           # 按下态
        BTN_PRESSED="#1C1C1C",       # 次级按钮按下
        BTN_HOVER="#242424",
        LINE="#2A2A2A",
        SCROLLBAR="#333333",
        SCROLLBAR_HOVER="#474747",
        TEXT_PRIMARY="#F5F5F5",
        TEXT_SECONDARY="#B5B5B5",
        TEXT_MUTED="#8A8A8A",
        TEXT_SUBTLE="#9E9E9E",
        TEXT_DISABLED="#555555",
        TEXT_FAINT="#4A4A4A",
        OFFLINE_CARD="#111111",
        OFFLINE_TEXT="#7E7E7E",
        OFFLINE_SUB="#666666",
        ICON_DIM="#9C9CA2",
        ICON_MUTED="#B5B5B5",
        HOME_HOVER="#CDCDCD",
        HOME_PRESSED="#999999",
        THUMB="#FFFFFF",               # 滑块拇指：深色模式白
        STATE_OFF="#3A3A3A",
        STATE_UNKNOWN_BG="#1C1C1C",
        STATE_UNKNOWN_BORDER="#343434",
        STATE_UNKNOWN_HOVER="#232323",
        ERROR_TEXT="#E05A5A",
        DEL_TEXT="#C06A6A",
        DEL_BORDER="#3A2A2A",
        DEL_BORDER_HOVER="#7A3333",
        WARN_BG="#332A14",
        WARN_BORDER="#5A4520",
        WARN_TEXT="#E2C07A",
    ),
}

# 当前主题；启动时由 theme_service.set_theme 写定
_current: str = "dark"


def current_theme() -> str:
    """当前主题名："dark" | "light"。"""
    return _current


def is_dark() -> bool:
    return _current == "dark"


def set_theme(theme: str) -> None:
    """切换当前调色板（仅改取色；全局刷新由 theme_service 编排）。"""
    global _current
    if theme not in PALETTES:
        raise ValueError(f"未知主题: {theme}")
    _current = theme


def palette() -> dict[str, str]:
    return PALETTES[_current]


class _PaletteMeta(type):
    """让 SiColors.XXX 动态代理当前调色板；强调色与固定色为独立取色。"""

    def __getattr__(cls, name: str) -> str:
        if name in _ACCENT_KEYS:
            return _accent_color(name)
        try:
            return PALETTES[_current][name]
        except KeyError:
            raise AttributeError(
                f"SiColors 无此语义色: {name}，可用键见 PALETTES/ACCENTS") from None


class SiColors(metaclass=_PaletteMeta):
    """语义色代理。THEME 系列与 ON_THEME_TEXT 随当前强调色取色；
    其余语义色随当前深/浅调色板取值；固定色为真属性。"""

    SWITCH_THUMB = SWITCH_THUMB
    DANGER = DANGER
    DANGER_TEXT = DANGER_TEXT
    WHITE = WHITE


def palette_for(mode: str):
    """固定调色板代理：属性接口与 SiColors 一致，但绑定指定明暗模式。

    桌面小组件可单独选择「浅色/深色」，不受全局主题影响：构建小组件
    内容时把代理注入 PowerButton / QuickOpsPopup 等组件，它们取色即
    从该代理读取，异步渲染的调节行也不会受全局主题切换影响。
    """
    if mode not in PALETTES:
        raise ValueError(f"未知调色板: {mode}")
    fixed = {
        k: getattr(SiColors, k)
        for k in vars(SiColors)
        if not k.startswith("_") and isinstance(getattr(SiColors, k), str)
    }
    # 强调色与明暗无关，固定浅/深的小组件同样跟随当前强调色
    for name in _ACCENT_KEYS:
        fixed[name] = _accent_color(name)
    import types
    return types.SimpleNamespace(**PALETTES[mode], **fixed)


# ----------------------------------------------------------------------------
# 全局 QSS 生成：模板占位符 $KEY，由当前调色板填充
# ----------------------------------------------------------------------------
_QSS_TEMPLATE = Template("""
* {
    font-family: "MiSans", "Microsoft YaHei UI", "Segoe UI";
    font-size: 10pt;
    color: $TEXT_PRIMARY;
}

QMainWindow, QDialog, QMessageBox {
    background: $WINDOW_BG;
}

QWidget#contentHost, QWidget#gridHost {
    background: $WINDOW_BG;
}

/* ---------- 内嵌标题栏（无边框窗口） ---------- */

QFrame#titleBar {
    background: $TITLE_BAR_BG;
    border-bottom: 1px solid $TITLE_BAR_BORDER;
}

QLabel#titleBarText {
    font-size: 9pt;
    font-weight: 600;
    color: $TEXT_SUBTLE;
    background: transparent;
}

QPushButton#titleBarBtn,
QPushButton#titleBarClose,
QPushButton#titleBarMax {
    background: transparent;
    border: none;
    border-radius: 4px;
    color: $TEXT_SUBTLE;
    font-family: "Segoe MDL2 Assets";
    font-size: 9pt;
}

QPushButton#titleBarBtn:hover {
    background: $SURFACE;
    color: $TEXT_PRIMARY;
}

QPushButton#titleBarMax:hover {
    background: $SURFACE;
    color: $TEXT_PRIMARY;
}

QPushButton#titleBarClose:hover {
    background: $DANGER;
    color: $WHITE;
}

QLabel#statusHint {
    color: $TEXT_SUBTLE;
    background: transparent;
    font-size: 9pt;
    padding: 4px 0;
}

/* ---------- 顶栏家庭切换器 ---------- */

QPushButton#homeSwitcher {
    background: transparent;
    border: none;
    padding: 2px 0;
    font-size: 17pt;
    font-weight: 600;
    color: $TEXT_PRIMARY;
    text-align: left;
}

QPushButton#homeSwitcher:hover {
    color: $HOME_HOVER;
}

QPushButton#homeSwitcher:pressed {
    color: $HOME_PRESSED;
}

/* ---------- 详情页功能卡片（电源行/滑块/模式/输入/只读） ---------- */

QFrame#propCard {
    background: $CARD;
    border: 1px solid $LINE;
    border-radius: 14px;
}
QFrame#propCard:hover {
    background: $CARD_HOVER;
    border-color: $CARD_BORDER_HOVER;
}

QPushButton#propCardToggle {
    background: transparent;
    border: none;
    color: $THEME;
    font-size: 9pt;
    padding: 2px 6px;
}

QPushButton#propCardToggle:hover {
    color: $THEME_HOVER;
}

/* ---------- 原生菜单（家庭切换/更多操作） ---------- */

QMenu#appMenu {
    background: $CARD;
    border: 1px solid $LINE;
    border-radius: 8px;
    padding: 4px;
}

QMenu#appMenu::item {
    padding: 5px 26px 5px 6px;
    border-radius: 6px;
    font-size: 10pt;
    text-align: left;
    color: $TEXT_PRIMARY;
}

QMenu#appMenu::item:selected {
    background: $BTN_HOVER;
}

QMenu#appMenu::item:checked {
    color: $THEME;
}

QMenu#appMenu::indicator {
    width: 12px;
    height: 12px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
    right: 6px;
}

/* ---------- 详情面板 ---------- */

QLabel#panelTitle {
    font-size: 15pt;
    font-weight: 600;
    color: $TEXT_PRIMARY;
}

QLabel#panelSubtitle {
    color: $TEXT_SECONDARY;
    font-size: 9pt;
}

QScrollArea {
    background: transparent;
}

QLabel {
    background: transparent;
}

/* ---------- 原生数值框（详情面板输入行） ---------- */

QSpinBox, QDoubleSpinBox {
    background: $CARD;
    border: 1px solid $LINE;
    border-radius: 8px;
    padding: 5px 10px;
    selection-background-color: $THEME;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: $THEME;
}

/* ---------- 滚动条 ---------- */

QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: $SCROLLBAR;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: $SCROLLBAR_HOVER;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    height: 0;
    background: none;
}

QScrollBar:horizontal {
    height: 0;
    background: transparent;
}

/* ---------- 通知浮层 ---------- */

QFrame#toastCard {
    background: $SURFACE;
    border: 1px solid $BTN_HOVER;
    border-radius: 10px;
}

/* ---------- 小爱语音悬浮球 ---------- */

QPushButton#voiceBall {
    background: $THEME;
    border: none;
    border-radius: 27px;
}
QPushButton#voiceBall:hover {
    background: $THEME_CHECKED_HOVER;
}
QPushButton#voiceBall:pressed {
    background: $THEME_DIM;
}

QFrame#voicePanel {
    background: $SURFACE;
    border: 1px solid $LINE;
    border-radius: 12px;
}
""")


def build_qss() -> str:
    """由当前调色板与强调色生成全局 QSS。"""
    values = dict(PALETTES[_current])
    # 模板里用到的强调色与固定色
    for name in _ACCENT_KEYS:
        values[name] = _accent_color(name)
    values.update(DANGER=DANGER, WHITE=WHITE)
    # 缺键早失败：模板新增占位符而某套调色板漏配时给出可读报错
    missing = set(_QSS_TEMPLATE.get_identifiers()) - set(values)
    assert not missing, f"QSS 模板占位符缺少调色板键: {missing}"
    return _QSS_TEMPLATE.substitute(values)


# ----------------------------------------------------------------------------
# siui 全局色组联动：SiCapsuleComboBox 弹层、tooltip 等内部件取色自这里
# ----------------------------------------------------------------------------

def sync_siui_colors() -> None:
    """把 siui 全局色组切到当前主题，并覆盖主题 token 为米家绿。

    siui 内置 Bright/Dark 两套色组；覆盖后 siui 内部件的青绿与
    应用主题色完全一致（内置 Bright 组的青绿偏亮，不是米家绿）。
    """
    from app.siui.core import SiColor, SiGlobal
    from app.siui.gui.color_group import BrightColorGroup, DarkColorGroup

    # 原地链到新色组而非重新绑定：siui 控件构造时缓存了色组引用，
    # 重新绑定会让未重建的旧控件继续用旧调色板
    group = SiGlobal.siui.colors
    reference = getattr(group, "reference", None)
    fresh = DarkColorGroup() if _current == "dark" else BrightColorGroup()
    fresh.assign(SiColor.THEME, _accent_color("THEME"))
    fresh.assign(SiColor.THEME_TRANSITION_A, _accent_color("THEME"))
    fresh.assign(SiColor.THEME_TRANSITION_B, _accent_color("THEME_HOVER"))
    fresh.assign(SiColor.SVG_THEME, _accent_color("THEME"))
    group.valid_state = False  # 本组命中即转 reference，绕过陈旧覆盖
    group.reference = fresh
    if reference is not None:
        fresh.reference = reference
    # 图标包默认色：浅色底上用深灰
    SiGlobal.siui.iconpack.setDefaultColor("#D1CBD4" if _current == "dark" else "#5f6368")


# ----------------------------------------------------------------------------
# siui 控件工厂（仅保留项目实际用到的）
# ----------------------------------------------------------------------------

def themed_switch() -> SiSwitchRefactor:
    """bool 属性用的开关，开启态轨道为主题色。"""
    switch = SiSwitchRefactor()
    switch.style_data.background_color_starting = QColor(SiColors.THEME)
    switch.style_data.background_color_ending = QColor(SiColors.THEME)
    switch.style_data.thumb_color_checked = QColor(SiColors.SWITCH_THUMB)
    switch.update()
    return switch


def themed_label(text: str = "", color: str | None = None) -> "SiLabelRefactor":
    """自绘文字标签，颜色不受全局 QSS 影响；缺省为主文字色。"""
    from app.siui.components.label import SiLabelRefactor

    label = SiLabelRefactor()
    label.setText(text)
    label.setTextColor(color or SiColors.TEXT_PRIMARY)
    # QFrame 子类卡片加 WA_StyledBackground 后，某些渲染路径会让
    # 无样式表的 SiLabel 背景按 palette 画成不透明色块，必须显式
    # 强制透明（widget 级样式表优先级最高，直接覆盖任何级联来源）
    label.setStyleSheet("background: transparent;")
    return label


def themed_tab_button(text: str) -> SiToggleButtonRefactor:
    """房间筛选 tab，选中态为主题青底深字。"""
    button = SiToggleButtonRefactor()
    button.setText(text)
    # siui 按钮的默认 size hint 偏大且水平可扩展，强制固定尺寸
    # 避免三个 tab 在整行里分散排布
    button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    button.style_data.button_color = QColor("#00" + SiColors.CARD[1:])
    button.style_data.text_color = QColor(SiColors.TEXT_SECONDARY)
    button.style_data.toggled_button_color = QColor(SiColors.THEME)
    button.style_data.toggled_text_color = QColor(SiColors.ON_THEME_TEXT)
    button.style_data.hover_color = QColor("#1a" + SiColors.THEME[1:])
    button.style_data.idle_color = QColor("#00" + SiColors.THEME[1:])
    button.style_data.click_color = QColor("#40" + SiColors.THEME[1:])
    button.reloadStyleData()
    return button


class _SelectAllLineEdit(QLineEdit):
    """editable 下拉的输入框：聚焦/点击时自动全选。

    用户点进输入框直接输入新数字即整体替换（否则光标在末尾，
    输入会追加到 "100" 后变 "1001"）。
    """

    def focusInEvent(self, event) -> None:  # noqa: N802
        super().focusInEvent(event)
        self.selectAll()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        super().mousePressEvent(event)
        self.selectAll()


def themed_combo(options: list[str], current: str = "",
                 editable: bool = False) -> "QComboBox":
    """设置页等处的下拉选择器：原生 QComboBox + 主题化样式。

    曾用过 siui 的 SiCapsuleComboBox，但其胶囊风格与设置页卡片
    不搭且依赖图标包资源，改回原生控件按调色板着色。

    editable=True 时允许直接键入任意文本（如缩放百分比），下拉仍
    提供预设档位；输入不会插入列表（保持档位干净）。
    """
    import qtawesome as qta
    from PySide6.QtWidgets import QLabel, QComboBox

    class _NoWheelCombo(QComboBox):
        """禁用滚轮 + 自绘主题色下拉三角的原生下拉框。

        QSS 的 border 三角技巧在 down-arrow 上会渲染成色块长条，
        改为子控件摆一个 qtawesome 三角图标，颜色随调色板。
        """

        def __init__(self):
            super().__init__()
            self._arrow = QLabel(self)
            self._arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        def set_arrow_color(self, color: str) -> None:
            self._arrow.setPixmap(qta.icon('mdi.chevron-down', color=color).pixmap(14, 14))

        def resizeEvent(self, event) -> None:  # noqa: N802
            super().resizeEvent(event)
            self._arrow.move(self.width() - 20, (self.height() - 14) // 2)

        def wheelEvent(self, event) -> None:  # noqa: N802
            # 禁用滚轮切换：设置页滚动浏览时容易误改选项
            event.ignore()

    combo = _NoWheelCombo()
    combo.addItems(options)
    if editable:
        combo.setEditable(True)
        # 键入文本不进列表，档位保持预设干净；回车/失焦提交由调用方处理
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        # 替换输入框为自动全选版：聚焦/点击即全选，直接输入整体替换
        combo.setLineEdit(_SelectAllLineEdit(combo))
        # 关键：移除 completer 关闭自动补全——否则输入 "12" 会被自动匹配
        # 替换成列表里的 "125%" 之类（用户反馈「输 2 变 75」即此）。
        # 必须在 setLineEdit 之后：setLineEdit 会重置 completer。
        combo.setCompleter(None)
        combo.setCurrentText(current)
    elif current and current in options:
        combo.setCurrentText(current)
    combo.setCursor(Qt.CursorShape.PointingHandCursor)
    combo.setFixedHeight(32)
    # 选项最多四个字，固定窄宽即可，避免被布局撑得过宽；
    # 可编辑下拉同样保持此宽度，与设置页其他下拉（如主题配色）一致。
    # 弹出列表异常（压缩成几像素）的原因是 drop-down 区被隐藏，
    # 由 apply_combo_qss(editable=True) 保留 24px 下拉区解决，与宽度无关。
    combo.setFixedWidth(112)
    apply_combo_qss(combo, editable=editable)
    combo.set_arrow_color(SiColors.TEXT_SECONDARY)
    return combo


def apply_combo_qss(combo, editable: bool = False) -> None:
    """下拉框与弹出列表按当前调色板着色（主题切换时重设）。

    editable=True 时保留 ::drop-down 区域宽度：可编辑下拉需要点
    下拉区才弹出列表（点正文是输入）；隐藏该区域会导致点不开。
    """
    combo.setStyleSheet(f"""
        QComboBox {{
            background: {SiColors.SURFACE};
            border: 1px solid {SiColors.LINE};
            border-radius: 8px;
            padding: 4px {8 if editable else 28}px 4px 12px;
            color: {SiColors.TEXT_PRIMARY};
            font-size: 9pt;
        }}
        QComboBox:hover {{ border-color: {SiColors.THEME}; }}
        QComboBox::drop-down {{ border: none; width: {24 if editable else 0}px; }}
        QComboBox::down-arrow {{ width: 0px; height: 0px; }}
        QComboBox QAbstractItemView {{
            background: {SiColors.CARD};
            border: 1px solid {SiColors.LINE};
            border-radius: 6px;
            color: {SiColors.TEXT_PRIMARY};
            selection-background-color: {SiColors.BTN_HOVER};
            selection-color: {SiColors.TEXT_PRIMARY};
            outline: none;
        }}
        QComboBox QLineEdit {{
            background: transparent;
            border: none;
            color: {SiColors.TEXT_PRIMARY};
        }}
    """)
