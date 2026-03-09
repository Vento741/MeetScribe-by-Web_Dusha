from __future__ import annotations

import logging
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk

from storage.exporter import format_duration

if TYPE_CHECKING:
    from app import MeetScribeApp

logger = logging.getLogger(__name__)


class HistoryView(ctk.CTkFrame):
    """История встреч с деревом папок, поиском и карточками."""

    def __init__(self, parent: ctk.CTkFrame, app: MeetScribeApp) -> None:
        super().__init__(parent, fg_color="transparent")
        self._app = app
        self._selected_folder_id: int | None = None
        self._drag_meeting = None
        self._drag_target_folder: int | None = None

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Левая панель: дерево папок ──
        self._folder_panel = ctk.CTkFrame(self, width=200)
        self._folder_panel.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        self._folder_panel.grid_propagate(False)
        self._folder_panel.grid_rowconfigure(1, weight=1)
        self._folder_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self._folder_panel, text="Папки", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, pady=(5, 0), padx=5, sticky="w")

        self._folder_scroll = ctk.CTkScrollableFrame(
            self._folder_panel, fg_color="transparent"
        )
        self._folder_scroll.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        self._folder_scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            self._folder_panel,
            text="+ Папка",
            width=80,
            height=28,
            command=self._create_folder,
        ).grid(row=2, column=0, pady=5)

        # ── Правая панель: поиск + список встреч ──
        right_panel = ctk.CTkFrame(self, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=1)

        search_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        search_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        search_frame.grid_columnconfigure(0, weight=1)

        self._search_entry = ctk.CTkEntry(
            search_frame, placeholder_text="Поиск по встречам..."
        )
        self._search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self._search_entry.bind("<Return>", lambda e: self._refresh())

        ctk.CTkButton(
            search_frame,
            text="Найти",
            width=80,
            command=self._refresh,
        ).grid(row=0, column=1)

        self._scroll = ctk.CTkScrollableFrame(right_panel)
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        self._refresh_folders()
        self._refresh()

    # ═══════════════════════ Папки ═══════════════════════

    def _refresh_folders(self) -> None:
        """Перестраивает дерево папок."""
        for w in self._folder_scroll.winfo_children():
            w.destroy()

        # "Все встречи"
        all_btn = ctk.CTkButton(
            self._folder_scroll,
            text="Все встречи",
            anchor="w",
            fg_color="transparent" if self._selected_folder_id is not None else None,
            text_color=("gray10", "gray90"),
            hover_color=("gray85", "gray25"),
            height=28,
            command=lambda: self._select_folder(None),
        )
        all_btn.grid(row=0, column=0, sticky="ew", pady=1)
        all_btn.bind("<Enter>", lambda e: self._on_folder_drag_enter(e, None))
        all_btn.bind("<Leave>", lambda e: self._on_folder_drag_leave(e))

        folders = self._app.db.list_folders()
        self._render_folder_tree(folders, parent_id=None, depth=0, start_row=1)

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
            btn = ctk.CTkButton(
                self._folder_scroll,
                text=f"{indent}📁 {folder['name']}",
                anchor="w",
                fg_color=None if is_selected else "transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray85", "gray25"),
                height=28,
                command=lambda f=fid: self._select_folder(f),
            )
            btn.grid(row=row, column=0, sticky="ew", pady=1)
            btn.bind("<Button-3>", lambda e, f=fid: self._folder_context_menu(e, f))
            btn.bind("<Enter>", lambda e, f=fid: self._on_folder_drag_enter(e, f))
            btn.bind("<Leave>", lambda e: self._on_folder_drag_leave(e))
            row += 1
            row = self._render_folder_tree(
                folders, parent_id=fid, depth=depth + 1, start_row=row
            )
        return row

    def _select_folder(self, folder_id: int | None) -> None:
        """Выбирает папку и обновляет список встреч."""
        self._selected_folder_id = folder_id
        self._refresh_folders()
        self._refresh()

    def _create_folder(self, parent_id: int | None = None) -> None:
        """Создаёт новую папку через диалог."""
        dialog = ctk.CTkInputDialog(
            text="Имя папки:",
            title="Новая папка",
        )
        name = dialog.get_input()
        if name and name.strip():
            self._app.db.create_folder(name.strip(), parent_id=parent_id)
            self._refresh_folders()

    def _folder_context_menu(self, event, folder_id: int) -> None:
        """Контекстное меню для папки."""
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
        dialog = ctk.CTkInputDialog(
            text="Новое имя:",
            title="Переименовать папку",
        )
        name = dialog.get_input()
        if name and name.strip():
            self._app.db.rename_folder(folder_id, name.strip())
            self._refresh_folders()

    def _delete_folder(self, folder_id: int) -> None:
        """Удаляет папку с подтверждением."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Удаление папки")
        dialog.geometry("350x120")
        dialog.grab_set()
        dialog.resizable(False, False)

        ctk.CTkLabel(
            dialog,
            text="Удалить папку?\nВстречи будут перемещены в корень.",
        ).pack(pady=15)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack()
        ctk.CTkButton(
            btn_frame,
            text="Удалить",
            fg_color="#c0392b",
            width=100,
            command=lambda: [
                self._app.db.delete_folder(folder_id),
                dialog.destroy(),
                self._select_folder(None),
            ],
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            btn_frame,
            text="Отмена",
            fg_color="gray",
            width=100,
            command=dialog.destroy,
        ).pack(side="left", padx=10)

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
            ctk.CTkLabel(self._scroll, text="Нет встреч", text_color="gray").grid(
                row=0,
                column=0,
                pady=40,
            )
            return

        for i, m in enumerate(meetings):
            self._create_meeting_card(m, i)

    def _create_meeting_card(self, meeting, row: int) -> None:
        """Создаёт карточку встречи с drag & drop и контекстным меню."""
        duration = format_duration(meeting.duration)
        card = ctk.CTkFrame(self._scroll, corner_radius=8)
        card.grid(row=row, column=0, sticky="ew", pady=3)
        card.grid_columnconfigure(1, weight=1)

        date_label = ctk.CTkLabel(card, text=meeting.date[:10], width=100)
        date_label.grid(row=0, column=0, padx=10, pady=8)

        title_label = ctk.CTkLabel(
            card,
            text=meeting.title or "Без названия",
            anchor="w",
            font=ctk.CTkFont(weight="bold"),
        )
        title_label.grid(row=0, column=1, sticky="w")

        dur_label = ctk.CTkLabel(card, text=duration, text_color="gray")
        dur_label.grid(row=0, column=2, padx=10)

        # Клик — открыть встречу
        for widget in (card, date_label, title_label, dur_label):
            widget.bind("<Button-1>", lambda e, mt=meeting: self._open_meeting(mt))
            widget.configure(cursor="hand2")

        # Правый клик — контекстное меню
        for widget in (card, date_label, title_label, dur_label):
            widget.bind(
                "<Button-3>", lambda e, mt=meeting: self._meeting_context_menu(e, mt)
            )

        # Drag & drop
        for widget in (card, date_label, title_label, dur_label):
            widget.bind(
                "<ButtonPress-1>",
                lambda e, mt=meeting: self._drag_start(e, mt),
                add="+",
            )
            widget.bind("<B1-Motion>", self._drag_motion)
            widget.bind("<ButtonRelease-1>", self._drag_end)

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
        ).pack(pady=20)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack()
        ctk.CTkButton(
            btn_frame,
            text="Удалить",
            fg_color="#c0392b",
            width=100,
            command=lambda: [
                self._app.db.delete_meeting(meeting.id),
                dialog.destroy(),
                self._refresh(),
                self._app.set_status(f"Встреча '{title}' удалена"),
            ],
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            btn_frame,
            text="Отмена",
            fg_color="gray",
            width=100,
            command=dialog.destroy,
        ).pack(side="left", padx=10)

    # ═══════════════════════ Drag & Drop ═══════════════════════

    def _drag_start(self, event, meeting) -> None:
        """Начало перетаскивания встречи."""
        self._drag_meeting = meeting
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def _drag_motion(self, event) -> None:
        """Движение при перетаскивании."""
        if self._drag_meeting is None:
            return
        # Визуальный фидбэк — курсор
        dx = abs(event.x_root - self._drag_start_x)
        dy = abs(event.y_root - self._drag_start_y)
        if dx > 5 or dy > 5:
            event.widget.configure(cursor="fleur")

    def _drag_end(self, event) -> None:
        """Окончание перетаскивания — перемещение в папку под курсором."""
        if self._drag_meeting is None:
            return

        event.widget.configure(cursor="hand2")

        if self._drag_target_folder is not None or self._drag_target_folder == 0:
            # Перемещаем в целевую папку
            target = self._drag_target_folder
            self._app.db.move_meeting(self._drag_meeting.id, target)
            self._refresh()
            self._app.set_status("Встреча перемещена")

        self._drag_meeting = None
        self._drag_target_folder = None

    def _on_folder_drag_enter(self, event, folder_id: int | None) -> None:
        """Подсветка папки при наведении во время drag."""
        if self._drag_meeting is not None:
            self._drag_target_folder = folder_id
            event.widget.configure(fg_color=("gray75", "gray35"))

    def _on_folder_drag_leave(self, event) -> None:
        """Снятие подсветки папки."""
        if self._drag_meeting is not None:
            self._drag_target_folder = None
            event.widget.configure(fg_color="transparent")

    # ═══════════════════════ Навигация ═══════════════════════

    def _open_meeting(self, meeting) -> None:
        """Открывает встречу в виде транскрипта/саммари."""
        full = self._app.db.get_meeting(meeting.id)
        if full:
            self._app.show_meeting(full)
        else:
            self._app.set_status("Не удалось загрузить встречу")
