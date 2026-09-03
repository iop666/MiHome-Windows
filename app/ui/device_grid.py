# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""设备卡片动画网格。

替代原 QGridLayout：卡片保持自身尺寸、列数随宽度自适应，布局与
QGridLayout 的观感一致（等分列、富余空间均匀落入列间距）。列数
变化时卡片平滑滑到新槽位，不再整批重建。

交互——右键拖动排序（类手机桌面整理图标）：
- 右键按住卡片超过拖拽阈值后，卡片浮起并跟随光标，被越过的卡片
  让位动画；
- 拖动贴住滚动区上下缘会自动滚动内容；
- 松开右键落位：卡片滑入槽位，发出 order_committed(当前视图 did
  新顺序)；未改变顺序时同样落位但不视为变更（主窗口侧去重）。
"""

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QScrollArea,
    QSizePolicy,
    QWidget,
)

from app.ui.device_card import DeviceCard

_SPACING = 14          # 卡片间距（与旧 QGridLayout spacing 一致）
_MARGIN_TOP = 4
_MARGIN_BOTTOM = 12
_COLUMN_HEADROOM = 12  # 计算列数时预留的右侧余量（沿用旧 _columns_for_width）
_MOVE_MS = 170         # 让位/落位动画时长
_REFLOW_DELAY_MS = 60  # 拖动窗口期间的重排防抖
_DRAG_EDGE_PX = 48     # 触发自动滚动的边缘距离
_DRAG_TICK_MS = 24     # 自动滚动节拍


class DeviceGrid(QWidget):
    """自适应列数的动画卡片网格容器（卡片由其直接管理，无布局）。"""

    order_committed = Signal(list)  # 落位后的当前视图 did 顺序
    drag_finished = Signal()        # 一次拖拽完全结束（含取消）

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("gridHost")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._cards: list[DeviceCard] = []
        self._cols = 0
        self._instant = True  # 卡片刚落位完成的排布不做动画，之后才动画

        self._anim: dict[int, QPropertyAnimation] = {}
        self._drag: DeviceCard | None = None
        self._drag_start_dids: list[str] | None = None
        self._press_card: DeviceCard | None = None
        self._press_global: QPoint | None = None
        self._drag_offset = QPoint()   # 光标到卡片原点的偏移（引擎坐标）
        self._edge_dir = 0
        self._resize_dirty = False

        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.setInterval(_REFLOW_DELAY_MS)
        self._reflow_timer.timeout.connect(self.reflow_if_needed)

        self._edge_timer = QTimer(self)
        self._edge_timer.setInterval(_DRAG_TICK_MS)
        self._edge_timer.timeout.connect(self._edge_scroll_tick)

    # ---------- 只读状态 ----------

    def dragging(self) -> bool:
        """是否有卡片正在拖拽（主窗口据此推迟重建）。"""
        return self._drag is not None

    def columns(self) -> int:
        return self._cols

    # ---------- 卡片装载与布局 ----------

    def set_cards(self, cards: list[DeviceCard]) -> None:
        """整体替换卡片列表（新卡片直接落位，不做入场动画）。"""
        for card in cards:
            card.setParent(self)
            card.installEventFilter(self)
            card.show()
        self._cards = list(cards)
        self._instant = True
        self._stop_all_animations()
        self.arrange(animate=False)
        self.reflow_if_needed()

    def arrange(self, animate: bool | None = None,
                frozen: set[DeviceCard] | None = None) -> None:
        """把卡片按当前列表顺序排布到各自槽位。

        animate=None 时按 _instant 决定（新卡片首次排布无声）；
        frozen 集合内的卡片不被移动（拖拽中的卡片跟手，不参与排布）。
        """
        if animate is None:
            animate = not self._instant
        if frozen is None:
            frozen = set()
        if not self._cards:
            self._instant = False
            return
        width = max(1, self.width())
        cols = self._column_count(width)
        card_w = self._cards[0].width()
        card_h = self._cards[0].height()
        rows = (len(self._cards) + cols - 1) // cols
        content_h = (_MARGIN_TOP + rows * card_h
                     + max(0, rows - 1) * _SPACING + _MARGIN_BOTTOM)
        if self.minimumHeight() != content_h:
            self.setMinimumHeight(content_h)
        self._cols = cols

        for index, card in enumerate(self._cards):
            if card in frozen or card is self._drag:
                continue
            target = self._slot_pos(index, cols, card_w, card_h, width)
            if card.pos() == target:
                continue
            if animate:
                self._animate_move(card, target)
            else:
                self._stop_anim(card)
                card.move(target)
        self._instant = False

    def reflow_if_needed(self) -> None:
        """防抖后的布局校正：列数/宽度变化时重排（拖动中则顺延）。"""
        if self._drag is not None:
            self._resize_dirty = True
            return
        if not self._cards:
            return
        width = max(1, self.width())
        cols = self._column_count(width)
        if cols != self._cols or self._instant:
            self.arrange(animate=not self._instant)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        super().resizeEvent(event)
        if not self._reflow_timer.isActive() and not self._drag:
            self._reflow_timer.start()

    # ---------- 布局几何 ----------

    def _column_count(self, width: int) -> int:
        """列数估算：沿用旧实现（卡片宽 + 间距按整列计，含右缘余量）。"""
        if not self._cards:
            return 0
        card_w = self._cards[0].width()
        eff = max(0, width - _COLUMN_HEADROOM)
        return max(1, (eff + _SPACING) // (card_w + _SPACING))

    def _slot_pos(self, index: int, cols: int, card_w: int, card_h: int,
                  width: int) -> QPoint:
        """第 index 张卡片的槽位原点（整数算法，与 QGridLayout 观感一致）。

        QGridLayout 对固定尺寸卡片的行为：富余空间
        E = W - cols*卡片宽 - (cols-1)*间距 平均分入 (cols+1) 个空隙，
        每个空隙一份 share=E//(cols+1)，列间空隙叠加基础间距；取整
        余数全部落到最右空隙。于是卡片起点 x = share + 列序*步长，
        步长 = 卡片宽 + 间距 + share（整数，无累积误差）。
        """
        leftover = width - cols * card_w - max(0, cols - 1) * _SPACING
        if cols <= 0 or leftover < 0:
            share = 0
        else:
            share = leftover // (cols + 1)
        step = card_w + _SPACING + share
        col = index % cols
        row = index // cols
        x = share + col * step
        y = _MARGIN_TOP + row * (card_h + _SPACING)
        return QPoint(x, y)

    # ---------- 位移动画 ----------

    def _animate_move(self, card: DeviceCard, pos: QPoint,
                      ms: int = _MOVE_MS) -> None:
        prev = self._anim.get(id(card))
        if prev is not None and prev.state() == QPropertyAnimation.State.Running:
            start = card.pos()
            prev.stop()
        else:
            start = card.pos()
        anim = QPropertyAnimation(card, b"geometry", card)
        anim.setDuration(ms)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(QRect(start, card.size()))
        anim.setEndValue(QRect(pos, card.size()))
        self._anim[id(card)] = anim
        anim.finished.connect(
            lambda c=card, a=anim: self._anim.pop(id(c), None)
            if self._anim.get(id(c)) is a else None)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _stop_anim(self, card: DeviceCard) -> None:
        anim = self._anim.pop(id(card), None)
        if anim is not None:
            anim.stop()

    def _stop_all_animations(self) -> None:
        for anim in list(self._anim.values()):
            anim.stop()
        self._anim.clear()

    # ---------- 右键拖拽 ----------

    def _card_for(self, obj) -> DeviceCard | None:
        while obj is not None:
            if isinstance(obj, DeviceCard):
                return obj
            obj = obj.parentWidget()
        return None

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt 命名约定)
        etype = event.type()
        # 拖拽进行中：鼠标已被 grabMouse 收拢到卡片，事件都从这里分流
        if self._drag is not None:
            if etype == QEvent.Type.MouseMove and event.buttons() & Qt.MouseButton.RightButton:
                self._on_drag_move(event)
                return True
            if etype == QEvent.Type.MouseButtonRelease \
                    and event.button() == Qt.MouseButton.RightButton:
                self._finish_drag(commit=True)
                return True
            if etype == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.RightButton:
                return True
            return False
        # 空闲状态：只关注右键按下/移动/释放
        if etype == QEvent.Type.MouseButtonPress \
                and event.button() == Qt.MouseButton.RightButton:
            card = self._card_for(obj)
            if card is not None:
                self._press_card = card
                self._press_global = event.globalPosition().toPoint()
            return card is not None
        if etype == QEvent.Type.MouseMove and self._press_card is not None \
                and event.buttons() & Qt.MouseButton.RightButton:
            if self._press_global is not None:
                moved = (event.globalPosition().toPoint()
                         - self._press_global).manhattanLength()
                if moved >= QApplication.startDragDistance():
                    self._start_drag(event)
            return True
        if etype == QEvent.Type.MouseButtonRelease \
                and event.button() == Qt.MouseButton.RightButton:
            self._press_card = None
            self._press_global = None
            return True
        if etype == QEvent.Type.MouseButtonDblClick \
                and event.button() == Qt.MouseButton.RightButton:
            return True
        return False

    def _start_drag(self, event) -> None:
        card = self._press_card
        if card is None or self._drag is not None:
            return
        self._press_card = None
        self._drag = card
        self._drag_start_dids = [c.device.did for c in self._cards]
        self._drag_offset = (self.mapFromGlobal(self._press_global)
                             - card.pos())
        self._edge_dir = 0
        card.raise_()
        # 浮起观感：柔和投影，卡片与网格拉开层次
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setColor(QColor(0, 0, 0, 110))
        shadow.setOffset(0, 6)
        shadow.setBlurRadius(36)
        card.setGraphicsEffect(shadow)
        card.grabMouse()
        self._on_drag_move(event)

    def _on_drag_move(self, event) -> None:
        card = self._drag
        if card is None:
            return
        gpos = event.globalPosition().toPoint()
        target = self.mapFromGlobal(gpos) - self._drag_offset
        # 横向留在内容区；纵向允许跟随到滚动内容以外（自动滚动承接）
        target.setX(max(0, min(target.x(), max(0, self.width() - card.width()))))
        card.move(target)
        self._update_hover(card)
        self._update_edge_scroll(gpos)

    def _update_hover(self, card: DeviceCard) -> None:
        """卡片中心落入其他卡片的“目标槽位”时让位换序。

        与动画中的卡片实时几何比较会来回抖动（让位动画未结束时
        卡片正处在移动途中）；改用槽位矩形判定，让位只按格跳变，
        行为与手机桌面整理一致。
        """
        width = max(1, self.width())
        cols = self._column_count(width)
        card_w, card_h = card.width(), card.height()
        center = QPoint(card.x() + card_w // 2, card.y() + card_h // 2)
        for index, other in enumerate(self._cards):
            if other is card:
                continue
            origin = self._slot_pos(index, cols, card_w, card_h, width)
            if QRect(origin, QSize(card_w, card_h)).contains(center):
                self._reorder_to(index)
                return

    def _reorder_to(self, index: int) -> None:
        card = self._drag
        if card is None:
            return
        current = self._cards.index(card)
        if index == current:
            return
        # 先取出拖拽卡片（其余卡片补位后 列表序号=槽位序号），再按
        # 悬停槽位插入：目标槽位即插入位置，无需按原位置修正
        self._cards.pop(current)
        self._cards.insert(index, card)
        # 让位动画：拖拽中的卡片保持跟手，其余卡片滑向新槽位
        self.arrange(animate=True, frozen={card})

    def _finish_drag(self, commit: bool) -> None:
        card = self._drag
        if card is None:
            return
        self._drag = None
        card.releaseMouse()
        card.setGraphicsEffect(None)
        self._edge_dir = 0
        self._edge_timer.stop()
        if commit:
            self.arrange(animate=True)  # 落位：卡片滑入最终槽位
            order = [c.device.did for c in self._cards]
            # 原样放回不算一次顺序变更（不触发持久化）
            if order != self._drag_start_dids:
                self.order_committed.emit(order)
        else:
            self.arrange(animate=True)
        self._drag_start_dids = None
        if self._resize_dirty:
            self._resize_dirty = False
        self.drag_finished.emit()

    # ---------- 拖拽自动滚动 ----------

    def _find_scroll_area(self) -> QScrollArea | None:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                return parent
            parent = parent.parentWidget()
        return None

    def _update_edge_scroll(self, gpos: QPoint) -> None:
        scroll = self._find_scroll_area()
        if scroll is None or scroll.viewport() is None:
            return
        viewport = scroll.viewport()
        local = viewport.mapFromGlobal(gpos)
        if local.y() < _DRAG_EDGE_PX:
            direction = -1
        elif local.y() > viewport.height() - _DRAG_EDGE_PX:
            direction = 1
        else:
            direction = 0
        if direction != self._edge_dir:
            self._edge_dir = direction
            if direction == 0:
                self._edge_timer.stop()
            elif not self._edge_timer.isActive():
                self._edge_timer.start()

    def _edge_scroll_tick(self) -> None:
        card = self._drag
        scroll = self._find_scroll_area()
        if card is None or scroll is None:
            self._edge_timer.stop()
            self._edge_dir = 0
            return
        bar = scroll.verticalScrollBar()
        if bar is None:
            self._edge_timer.stop()
            return
        gpos = QCursor.pos()
        self._update_edge_scroll(gpos)
        if self._edge_dir == 0:
            self._edge_timer.stop()
            return
        step = 10
        before = bar.value()
        bar.setValue(before + self._edge_dir * step)
        delta = bar.value() - before
        if delta == 0:
            # 已滚到头：继续贴着也不会有新内容，停掉节拍避免空转
            self._edge_dir = 0
            self._edge_timer.stop()
            return
        # 滚动即内容移动：卡片反向补位保持跟手，再重算让位目标
        card.move(card.x(), card.y() + delta)
        self._update_hover(card)
