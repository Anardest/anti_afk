import threading
import tkinter as tk
from tkinter import messagebox, ttk

from pynput.keyboard import Key, Listener
from pynput.mouse import Button, Controller


class AutoClickerApp:
    MIN_INTERVAL = 0.01
    MAX_INTERVAL = 3600.0

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Автокликер")
        self.root.resizable(False, False)

        self.mouse = Controller()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.is_running = False
        self.closing = False
        self.hotkey_listener: Listener | None = None

        self.interval_var = tk.StringVar(value="1.0")
        self.offset_x_var = tk.StringVar(value="100")
        self.offset_y_var = tk.StringVar(value="0")
        self.status_var = tk.StringVar(value="Остановлен")
        self.hotkey_var = tk.StringVar(
            value="Горячая клавиша: Левый Shift — остановить"
        )

        self._build_ui()
        self._start_hotkey_listener()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=18)
        container.grid(row=0, column=0, sticky="nsew")

        ttk.Label(
            container,
            text="Автоматическое нажатие левой кнопки мыши",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        ttk.Label(container, text="Интервал между кликами (сек.):").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=3
        )
        self.interval_entry = ttk.Entry(
            container, textvariable=self.interval_var, width=12
        )
        self.interval_entry.grid(row=1, column=1, sticky="w", pady=3)

        ttk.Separator(container).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=10
        )
        ttk.Label(
            container,
            text="Смещение курсора относительно исходной позиции",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 6))

        ttk.Label(container, text="X (вправо + / влево −):").grid(
            row=4, column=0, sticky="w", padx=(0, 10), pady=3
        )
        self.offset_x_entry = ttk.Entry(
            container, textvariable=self.offset_x_var, width=12
        )
        self.offset_x_entry.grid(row=4, column=1, sticky="w", pady=3)

        ttk.Label(container, text="Y (вниз + / вверх −):").grid(
            row=5, column=0, sticky="w", padx=(0, 10), pady=3
        )
        self.offset_y_entry = ttk.Entry(
            container, textvariable=self.offset_y_var, width=12
        )
        self.offset_y_entry.grid(row=5, column=1, sticky="w", pady=3)

        self.start_button = ttk.Button(
            container, text="Старт", command=self._start_clicking
        )
        self.start_button.grid(row=6, column=0, sticky="ew", pady=(16, 10), padx=(0, 5))

        self.stop_button = ttk.Button(
            container, text="Стоп", command=self._request_stop, state="disabled"
        )
        self.stop_button.grid(row=6, column=1, sticky="ew", pady=(16, 10), padx=(5, 0))

        ttk.Separator(container).grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=8
        )
        ttk.Label(container, textvariable=self.status_var).grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(3, 5)
        )
        ttk.Label(container, textvariable=self.hotkey_var).grid(
            row=9, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            container,
            text="Цикл: смещение → клик → исходная позиция → клик.",
            foreground="#666666",
        ).grid(row=10, column=0, columnspan=2, sticky="w", pady=(10, 0))

        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)
        self.root.geometry("475x390")

    def _start_hotkey_listener(self) -> None:
        try:
            # Отслеживаем именно левый Shift, не правый.
            self.hotkey_listener = Listener(on_press=self._on_key_press)
            self.hotkey_listener.start()
        except Exception as exc:
            self.hotkey_var.set(
                "Горячая клавиша недоступна; используйте кнопку «Стоп»."
            )
            print(f"Не удалось запустить обработчик горячей клавиши: {exc}")

    def _on_key_press(self, key) -> None:
        if key == Key.shift_l:
            self._on_hotkey()

    def _on_hotkey(self) -> None:
        # Callback вызывается из отдельного потока pynput.
        if self.closing:
            return
        self.stop_event.set()
        try:
            self.root.after(0, self._show_stopping_status)
        except RuntimeError:
            # Окно уже закрывается.
            pass

    def _show_stopping_status(self) -> None:
        if self.is_running:
            self.status_var.set("Получена команда остановки…")

    def _start_clicking(self) -> None:
        if self.is_running:
            return

        raw_interval = self.interval_var.get().strip().replace(",", ".")
        try:
            interval = float(raw_interval)
        except ValueError:
            messagebox.showerror(
                "Некорректный интервал",
                "Введите число, например 1 или 0.5.",
                parent=self.root,
            )
            return

        if not self.MIN_INTERVAL <= interval <= self.MAX_INTERVAL:
            messagebox.showerror(
                "Некорректный интервал",
                "Интервал должен быть от 0.01 до 3600 секунд.",
                parent=self.root,
            )
            return

        try:
            offset_x = int(self.offset_x_var.get().strip())
            offset_y = int(self.offset_y_var.get().strip())
        except ValueError:
            messagebox.showerror(
                "Некорректное смещение",
                "Смещение X и Y должно быть целым числом пикселей. Можно использовать минус.",
                parent=self.root,
            )
            return

        try:
            origin = tuple(self.mouse.position)
        except Exception as exc:
            messagebox.showerror(
                "Ошибка мыши", f"Не удалось получить положение курсора: {exc}",
                parent=self.root,
            )
            return

        self.stop_event.clear()
        self.is_running = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._set_settings_state("disabled")
        self.status_var.set(
            f"Работает — интервал {interval:g} сек., смещение X={offset_x}, Y={offset_y}"
        )

        self.worker = threading.Thread(
            target=self._click_loop,
            args=(interval, origin, offset_x, offset_y),
            name="AutoClickerWorker",
            daemon=True,
        )
        self.worker.start()

    def _click_loop(
        self, interval: float, origin: tuple[int, int], offset_x: int, offset_y: int
    ) -> None:
        error_message = None
        target = (origin[0] + offset_x, origin[1] + offset_y)

        try:
            while not self.stop_event.is_set():
                # Клик в точке со смещением.
                self.mouse.position = target
                self.mouse.click(Button.left, 1)
                if self.stop_event.wait(interval):
                    break

                # Возврат в исходную точку и второй клик.
                self.mouse.position = origin
                self.mouse.click(Button.left, 1)
                if self.stop_event.wait(interval):
                    break
        except Exception as exc:
            error_message = str(exc)
        finally:
            # Даже при остановке или ошибке возвращаем курсор туда,
            # где он находился в момент нажатия кнопки «Старт».
            try:
                self.mouse.position = origin
            except Exception as exc:
                if error_message is None:
                    error_message = f"Не удалось вернуть курсор в исходную позицию: {exc}"

            if not self.closing:
                try:
                    self.root.after(0, lambda: self._on_worker_finished(error_message))
                except RuntimeError:
                    pass

    def _set_settings_state(self, state: str) -> None:
        self.interval_entry.configure(state=state)
        self.offset_x_entry.configure(state=state)
        self.offset_y_entry.configure(state=state)

    def _request_stop(self) -> None:
        if self.is_running:
            self.stop_event.set()
            self.status_var.set("Останавливается…")
            self.stop_button.configure(state="disabled")

    def _on_worker_finished(self, error_message: str | None = None) -> None:
        self.is_running = False
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self._set_settings_state("normal")

        if error_message:
            self.status_var.set("Остановлен из-за ошибки")
            messagebox.showerror(
                "Ошибка автокликера", error_message, parent=self.root
            )
        else:
            self.status_var.set("Остановлен")

    def _on_close(self) -> None:
        self.closing = True
        self.stop_event.set()

        if self.hotkey_listener is not None:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass

        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
