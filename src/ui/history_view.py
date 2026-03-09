from __future__ import annotations

import logging
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk

from storage.exporter import format_duration

if TYPE_CHECKING:
    from app import MeetScribeApp

logger = logging.getLogger(__name__)

# ── Цветовая палитра ──
_ACCENT = "#2BA5B5"
_ACCENT_HOVER = "#239BA8"
_ACCENT_DIM = "#1E3A3F"
_CARD_BG = ("gray92", "gray17")
_CARD_HOVER = ("gray88", "gray22")
_CARD_DRAG = ("gray82", "gray28")
_DROP_HIGHLIGHT = ("#D4F5F5", "#1A4040")
_DATE_COLOR = ("gray45", "gray60")
_DUR_COLOR = ("gray50", "gray55")
_DANGER = "#C0392B"
_DANGER_HOVER = "#E74C3C"

# Минимальное смещение мыши для начала перетаскивания
_DRAG_THRESHOLD = 8


class HistoryView(ctk.CTkFrame):
    """История встреч с деревом папок, поиском и карточками."""

    def __init__(self, parent: ctk.CTkFrame, app: MeetScribeApp) -> None:
        super().__init__(parent, fg_color="transparent")
        self._app = app
        self._selected_folder_id: int | None = None

        # Drag & drop state
        self._drag_meeting = None
        self._drag_active = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._drag_ghost: tk.Toplevel | None = None
        self._drag_source_card: ctk.CTkFrame | None = None
        self._highlighted_folder_widget: ctk.CTkButton | None = None

        # Маппинг виджетов папок → folder_id для winfo_containing
        self._folder_widget_map: dict[str, int | None] = {}

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_folder_panel()
        self._build_meetings_panel()
        self._refresh_folders()
        self._refresh()

    # ═══════════════════════ Построение UI ═══════════════════════

    def _build_folder_panel(self) -> None:
        """Строит левую панель с деревом папок."""
        self._folder_panel = ctk.CTkFrame(
            self, width=210, corner_radius=12,
            border_width=1, border_color=("gray80", "gray25"),
        )
        self._folder_panel.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        self._folder_panel.grid_propagate(False)
        self._folder_panel.grid_rowconfigure(1, weight=1)
        self._folder_panel.grid_columnconfigure(0, weight=1)

        # Заголовок
        header = ctk.CTkFrame(self._folder_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Папки",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=_ACCENT,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header, text="+", width=28, height=28,
            corner_radius=6, font=ctk.CTkFont(size=16),
            fg_color="transparent",
            hover_color=("gray85", "gray25"),
            text_color=_ACCENT,
            command=self._create_folder,
        ).grid(row=0, column=1)

        # Скролл папок
        self._folder_scroll = ctk.CTkScrollableFrame(
            self._folder_panel, fg_color="transparent",
        )
        self._folder_scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 8))
        self._folder_scroll.grid_columnconfigure(0, weight=1)

    def _build_meetings_panel(self) -> None:
        """Строит правую панель с поиском и списком встреч."""
        right_panel = ctk.CTkFrame(self, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=1)

        # Поиск
        search_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        search_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        search_frame.grid_columnconfigure(0, weight=1)

        self._search_entry = ctk.CTkEntry(
            search_frame, placeholder_text="Поиск по встречам...",
            height=36, corner_radius=8,
            border_color=("gray75", "gray30"),
        )
        self._search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._search_entry.bind("<Return>", lambda e: self._refresh())

        ctk.CTkButton(
            search_frame, text="Найти", width=80, height=36,
            corner_radius=8, fg_color=_ACCENT, hover_color=_ACCENT_HOVER,
            command=self._refresh,
        ).grid(row=0, column=1)

        # Список встреч
        self._scroll = ctk.CTkScrollableFrame(
            right_panel, corner_radius=12,
            border_width=1, border_color=("gray80", "gray25"),
        )
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

    # ═══════════════════════ Папки ═══════════════════════

    def _refresh_folders(self) -> None:
        """Перестраивает дерево папок."""
        for w in self._folder_scroll.winfo_children():
            w.destroy()
        self._folder_widget_map.clear()

        # «Все встречи»
        all_btn = self._make_folder_button(
            "Все встречи", folder_id=None,
            is_selected=(self._selected_folder_id is None),
        )
        all_btn.grid(row=0, column=0, sticky="ew", pady=(2, 1))

        folders = self._app.db.list_folders()
        self._render_folder_tree(folders, parent_id=None, depth=0, start_row=1)

    def _make_folder_button(
        self, text: str, folder_id: int | None, is_selected: bool = False,
    ) -> ctk.CTkButton:
        """Создаёт кнопку папки и регистрирует её в маппинге."""
        btn = ctk.CTkButton(
            self._folder_scroll, text=text, anchor="w",
            fg_color=_ACCENT_DIM if is_selected else "transparent",
            text_color=(_ACCENT if is_selected else ("gray10", "gray90")),
            hover_color=("gray85", "gray25"),
            height=30, corner_radius=6,
            font=ctk.CTkFont(
                weight="bold" if is_selected else "normal",
            ),
            command=lambda: self._select_folder(folder_id),
        )
        btn.bind("<Button-3>", lambda e, f=folder_id: self._folder_context_menu(e, f))
        # Регистрируем виджет для drag & drop
        self._folder_widget_map[str(btn)] = folder_id
        # Регистрируем внутренние виджеты CTkButton (label, canvas)
        self._register_children(btn, folder_id)
        return btn

    def _register_children(self, widget: tk.Widget, folder_id: int | None) -> None:
        """Регистрирует дочерние виджеты для корректного winfo_containing."""
        for child in widget.winfo_children():
            self._folder_widget_map[str(child)] = folder_id
            self._register_children(child, folder_id)

    def _render_folder_tree(
        self,
        folders: list[dict],
        parent_id: int | None,
        depth: int,
        start_row: int,
    ) -> int:
        """Рекурсивно рендерит вложенные папки."""
        row = start_row
        children = [f for f in folders if f["parent_id"] == parent_id]
        for folder in children:
            fid = folder["id"]
            is_selected = self._selected_folder_id == fid
            indent = "  " * depth
            btn = self._make_folder_button(
                f"{indent}📁 {folder['name']}",
                folder_id=fid,
                is_selected=is_selected,
            )
            btn.grid(row=row, column=0, sticky="ew", pady=1)
            row += 1
            row = self._render_folder_tree(
                folders, parent_id=fid, depth=depth + 1, start_row=row,
            )
        return row

    def _select_folder(self, folder_id: int | None) -> None:
        """Выбирает папку и обновляет список встреч."""
        self._selected_folder_id = folder_id
        self._refresh_folders()
        self._refresh()

    def _create_folder(self, parent_id: int | None = None) -> None:
        """Создаёт новую папку через диалог."""
        dialog = ctk.CTkInputDialog(text="Имя папки:", title="Новая папка")
        name = dialog.get_input()
        if name and name.strip():
            self._app.db.create_folder(name.strip(), parent_id=parent_id)
            self._refresh_folders()

    def _folder_context_menu(self, event, folder_id: int | None) -> None:
        """Контекстное меню для папки."""
        if folder_id is None:
            return  # «Все встречи» — без контекстного меню
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Создать подпапку",
            command=lambda: self._create_folder(parent_id=folder_id),
        )
        menu.add_command(
            label="Переименовать",
            command=lambda: self._rename_folder(folder_id),
        )
        menu.add_separator()
        menu.add_command(
            label="Удалить",
            command=lambda: self._delete_folder(folder_id),
        )
        menu.tk_popup(event.x_root, event.y_root)

    def _rename_folder(self, folder_id: int) -> None:
        """Переименовывает папку."""
        dialog = ctk.CTkInputDialog(text="Новое имя:", title="Переименовать папку")
        name = dialog.get_input()
        if name and name.strip():
            self._app.db.rename_folder(folder_id, name.strip())
            self._refresh_folders()

    def _delete_folder(self, folder_id: int) -> None:
        """Удаляет папку с подтверждением."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Удаление папки")
        dialog.geometry("350x130")
        dialog.grab_set()
        dialog.resizable(False, False)

        ctk.CTkLabel(
            dialog,
            text="Удалить папку?\nВстречи будут перемещены в корень.",
            font=ctk.CTkFont(size=13),
        ).pack(pady=(20, 15))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack()
        ctk.CTkButton(
            btn_frame, text="Удалить", width=110,
            fg_color=_DANGER, hover_color=_DANGER_HOVER,
            corner_radius=8,
            command=lambda: [
                self._app.db.delete_folder(folder_id),
                dialog.destroy(),
                self._select_folder(None),
            ],
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            btn_frame, text="Отмена", width=110,
            fg_color="gray", corner_radius=8,
            command=dialog.destroy,
        ).pack(side="left", padx=8)

    # ═══════════════════════ Встречи ═══════════════════════

    def _refresh(self) -> None:
        """Обновляет список встреч."""
        for widget in self._scroll.winfo_children():
            widget.destroy()

        query = self._search_entry.get().strip()
        if query:
            meetings = self._app.db.search(query, lightweight=True)
        else:
            meetings = self._app.db.list_meetings(
                lightweight=True,
                folder_id=self._selected_folder_id,
            )

        if not meetings:
            ctk.CTkLabel(
                self._scroll, text="Нет встреч",
                text_color=_DATE_COLOR, font=ctk.CTkFont(size=14),
            ).grid(row=0, column=0, pady=50)
            return

        for i, m in enumerate(meetings):
            self._create_meeting_card(m, i)

    def _create_meeting_card(self, meeting, row: int) -> None:
        """Создаёт компактную карточку встречи с drag & drop и контекстным меню."""
        duration = format_duration(meeting.duration)

        card = ctk.CTkFrame(
            self._scroll, corner_radius=6,
            fg_color=_CARD_BG,
            border_width=1, border_color=("gray82", "gray22"),
        )
        card.grid(row=row, column=0, sticky="ew", pady=2, padx=4)
        card.grid_columnconfigure(2, weight=1)

        # Акцент-полоска слева
        accent_bar = ctk.CTkFrame(
            card, width=3, corner_radius=1, fg_color=_ACCENT,
        )
        accent_bar.grid(row=0, column=0, sticky="ns", padx=(4, 6), pady=6)

        # Дата
        date_label = ctk.CTkLabel(
            card, text=meeting.date[:10],
            text_color=_DATE_COLOR,
            font=ctk.CTkFont(size=11), width=72,
        )
        date_label.grid(row=0, column=1, padx=(0, 6), pady=5)

        # Название + папка в одну строку
        title_text = meeting.title or "Без названия"
        if meeting.folder_id is not None:
            folders = self._app.db.list_folders()
            folder_name = next(
                (f["name"] for f in folders if f["id"] == meeting.folder_id), None,
            )
            if folder_name:
                title_text = f"{title_text}  ·  📁 {folder_name}"

        title_label = ctk.CTkLabel(
            card, text=title_text, anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        title_label.grid(row=0, column=2, sticky="ew", pady=5)

        # Длительность
        dur_label = ctk.CTkLabel(
            card, text=duration, text_color=_DUR_COLOR,
            font=ctk.CTkFont(size=11),
        )
        dur_label.grid(row=0, column=3, padx=(6, 10), pady=5)

        # Все виджеты для биндинга
        widgets = [card, date_label, title_label, dur_label, accent_bar]

        for widget in widgets:
            widget.configure(cursor="hand2")
            # Клик — открыть встречу (только если не было drag)
            widget.bind("<Button-1>", lambda e, mt=meeting: self._on_card_click(e, mt))
            # Правый клик — контекстное меню
            widget.bind(
                "<Button-3>",
                lambda e, mt=meeting: self._meeting_context_menu(e, mt),
            )
            # Drag & drop
            widget.bind(
                "<ButtonPress-1>",
                lambda e, mt=meeting, c=card: self._drag_start(e, mt, c),
                add="+",
            )
            widget.bind("<B1-Motion>", self._drag_motion)
            widget.bind("<ButtonRelease-1>", self._drag_end)

        # Hover-эффект на карточку
        for widget in widgets:
            widget.bind("<Enter>", lambda e, c=card: self._card_hover(c, True), add="+")
            widget.bind("<Leave>", lambda e, c=card: self._card_hover(c, False), add="+")

    def _card_hover(self, card: ctk.CTkFrame, enter: bool) -> None:
        """Подсветка карточки при наведении."""
        if self._drag_active:
            return
        card.configure(fg_color=_CARD_HOVER if enter else _CARD_BG)

    def _on_card_click(self, event, meeting) -> None:
        """Обрабатывает клик — открывает встречу, если не было drag."""
        # Открытие произойдёт в _drag_end, если не было перетаскивания

    def _meeting_context_menu(self, event, meeting) -> None:
        """Контекстное меню для карточки встречи."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Открыть", command=lambda: self._open_meeting(meeting))

        # Подменю перемещения в папку
        move_menu = tk.Menu(menu, tearoff=0)
        if meeting.folder_id is not None:
            move_menu.add_command(
                label="В корень",
                command=lambda: self._move_meeting(meeting.id, None),
            )
            move_menu.add_separator()
        folders = self._app.db.list_folders()
        for f in folders:
            if f["id"] != meeting.folder_id:
                move_menu.add_command(
                    label=f["name"],
                    command=lambda fid=f["id"]: self._move_meeting(meeting.id, fid),
                )
        if folders or meeting.folder_id is not None:
            menu.add_cascade(label="Переместить в...", menu=move_menu)

        menu.add_separator()
        menu.add_command(label="Удалить", command=lambda: self._confirm_delete(meeting))
        menu.tk_popup(event.x_root, event.y_root)

    def _move_meeting(self, meeting_id: int, folder_id: int | None) -> None:
        """Перемещает встречу в папку."""
        self._app.db.move_meeting(meeting_id, folder_id)
        self._refresh()
        self._app.set_status("Встреча перемещена")

    def _confirm_delete(self, meeting) -> None:
        """Диалог подтверждения удаления встречи."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Удаление")
        dialog.geometry("400x150")
        dialog.grab_set()
        dialog.resizable(False, False)

        title = meeting.title or "Без названия"
        ctk.CTkLabel(
            dialog,
            text=f"Удалить '{title}'?\nАудиофайл тоже будет удалён.",
            font=ctk.CTkFont(size=13),
        ).pack(pady=(20, 15))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack()
        ctk.CTkButton(
            btn_frame, text="Удалить", width=110,
            fg_color=_DANGER, hover_color=_DANGER_HOVER,
            corner_radius=8,
            command=lambda: [
                self._app.db.delete_meeting(meeting.id),
                dialog.destroy(),
                self._refresh(),
                self._app.set_status(f"Встреча '{title}' удалена"),
            ],
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            btn_frame, text="Отмена", width=110,
            fg_color="gray", corner_radius=8,
            command=dialog.destroy,
        ).pack(side="left", padx=8)

    # ═══════════════════════ Drag & Drop ═══════════════════════

    def _drag_start(self, event, meeting, card: ctk.CTkFrame) -> None:
        """Запоминает начальную позицию для определения drag."""
        self._drag_meeting = meeting
        self._drag_source_card = card
        self._drag_active = False
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def _drag_motion(self, event) -> None:
        """Движение мыши — определяет начало drag и подсвечивает цель."""
        if self._drag_meeting is None:
            return

        dx = abs(event.x_root - self._drag_start_x)
        dy = abs(event.y_root - self._drag_start_y)

        # Активация drag при достаточном смещении
        if not self._drag_active and (dx > _DRAG_THRESHOLD or dy > _DRAG_THRESHOLD):
            self._drag_active = True
            self._create_drag_ghost(event)
            if self._drag_source_card:
                self._drag_source_card.configure(fg_color=_CARD_DRAG)

        if not self._drag_active:
            return

        # Двигаем ghost
        if self._drag_ghost:
            self._drag_ghost.geometry(
                f"+{event.x_root + 12}+{event.y_root - 8}"
            )

        # Определяем папку под курсором через winfo_containing
        target_widget = self.winfo_toplevel().winfo_containing(
            event.x_root, event.y_root,
        )
        target_folder_id = self._folder_widget_map.get(
            str(target_widget) if target_widget else "", "__miss__",
        )

        # Подсветка целевой папки
        if target_folder_id != "__miss__":
            self._highlight_folder_target(target_widget, target_folder_id)
        else:
            self._clear_folder_highlight()

    def _create_drag_ghost(self, event) -> None:
        """Создаёт плавающий индикатор перетаскивания."""
        if self._drag_ghost:
            return
        title = self._drag_meeting.title or "Без названия"
        ghost = tk.Toplevel(self)
        ghost.overrideredirect(True)
        ghost.attributes("-alpha", 0.85)
        ghost.attributes("-topmost", True)
        ghost.geometry(f"+{event.x_root + 12}+{event.y_root - 8}")

        frame = tk.Frame(ghost, bg="#2BA5B5", padx=10, pady=6)
        frame.pack()
        tk.Label(
            frame, text=f"📋 {title[:30]}",
            bg="#2BA5B5", fg="white",
            font=("Segoe UI", 10, "bold"),
        ).pack()

        self._drag_ghost = ghost

    def _destroy_drag_ghost(self) -> None:
        """Уничтожает ghost."""
        if self._drag_ghost:
            self._drag_ghost.destroy()
            self._drag_ghost = None

    def _highlight_folder_target(
        self, widget: tk.Widget, folder_id: int | None,
    ) -> None:
        """Подсвечивает папку-цель для дропа."""
        # Ищем родительский CTkButton
        btn = self._find_folder_button(widget)
        if btn is self._highlighted_folder_widget:
            return
        self._clear_folder_highlight()
        if btn:
            btn.configure(fg_color=_DROP_HIGHLIGHT, text_color=_ACCENT)
            self._highlighted_folder_widget = btn

    def _find_folder_button(self, widget: tk.Widget) -> ctk.CTkButton | None:
        """Находит CTkButton-папку по виджету или его родителям."""
        w = widget
        for _ in range(5):  # Максимум 5 уровней вложенности
            if isinstance(w, ctk.CTkButton) and str(w) in self._folder_widget_map:
                return w
            if w.master is None:
                break
            w = w.master
        return None

    def _clear_folder_highlight(self) -> None:
        """Снимает подсветку с текущей выделенной папки."""
        if self._highlighted_folder_widget:
            # Восстанавливаем оригинальный цвет
            folder_id = self._folder_widget_map.get(
                str(self._highlighted_folder_widget),
            )
            is_selected = folder_id == self._selected_folder_id
            self._highlighted_folder_widget.configure(
                fg_color=_ACCENT_DIM if is_selected else "transparent",
                text_color=(_ACCENT if is_selected else ("gray10", "gray90")),
            )
            self._highlighted_folder_widget = None

    def _drag_end(self, event) -> None:
        """Завершает перетаскивание или открывает встречу."""
        meeting = self._drag_meeting
        was_drag = self._drag_active

        # Определяем цель дропа до очистки
        target_folder_id = None
        has_target = False
        if was_drag:
            target_widget = self.winfo_toplevel().winfo_containing(
                event.x_root, event.y_root,
            )
            result = self._folder_widget_map.get(
                str(target_widget) if target_widget else "", "__miss__",
            )
            if result != "__miss__":
                target_folder_id = result
                has_target = True

        # Очистка drag state
        self._destroy_drag_ghost()
        self._clear_folder_highlight()
        if self._drag_source_card:
            self._drag_source_card.configure(fg_color=_CARD_BG)
        self._drag_meeting = None
        self._drag_source_card = None
        self._drag_active = False

        if meeting is None:
            return

        if was_drag and has_target:
            # Дроп в папку
            self._app.db.move_meeting(meeting.id, target_folder_id)
            self._refresh()
            self._app.set_status("Встреча перемещена")
        elif not was_drag:
            # Обычный клик — открыть встречу
            self._open_meeting(meeting)

    # ═══════════════════════ Навигация ═══════════════════════

    def _open_meeting(self, meeting) -> None:
        """Открывает встречу в виде транскрипта/саммари."""
        full = self._app.db.get_meeting(meeting.id)
        if full:
            self._app.show_meeting(full)
        else:
            self._app.set_status("Не удалось загрузить встречу")
