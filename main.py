import argparse
import calendar
import datetime
import json
import os
import sys
import tkinter as tk
from tkinter import scrolledtext

CONFIG = {
    "vfs_path": "",
    "script_path": "",
}

VFS_DATA = {}
CURRENT_PATH = ["/"]


def expand_env_vars(text: str) -> str:
    """Подставляет переменные окружения типа $HOME или %USER%."""
    return os.path.expandvars(text)


def parse_args():
    """Разбирает аргументы командной строки."""
    parser = argparse.ArgumentParser(description="VFS Emulator")
    parser.add_argument(
        "--vfs-path",
        "-v",
        type=str,
        default="",
        help="Путь к JSON файлу VFS",
    )
    parser.add_argument(
        "--script-path",
        "-s",
        type=str,
        default="",
        help="Путь к стартовому скрипту",
    )
    args = parser.parse_args()
    CONFIG["vfs_path"] = args.vfs_path
    CONFIG["script_path"] = args.script_path


def load_vfs(path: str):
    """Загружает структуру VFS из JSON файла в память."""
    global VFS_DATA
    if not path:
        VFS_DATA = {"type": "dir", "name": "/", "children": {}}
        return

    if not os.path.exists(path):
        print(f"Ошибка: Файл VFS '{path}' не найден.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(path, "r", encoding="utf-8") as f:
            VFS_DATA = json.load(f)
    except Exception as err:
        print(f"Ошибка чтения VFS JSON: {err}", file=sys.stderr)
        sys.exit(1)


def get_node_by_path(path_str: str):
    """Возвращает узел VFS по пути и список разрешенных сегментов."""
    if path_str.startswith("/"):
        parts = [p for p in path_str.split("/") if p]
    else:
        current_clean = [p for p in CURRENT_PATH if p != "/"]
        relative_parts = [p for p in path_str.split("/") if p]
        parts = current_clean + relative_parts

    resolved = []
    for item in parts:
        if item == ".":
            continue
        elif item == "..":
            if resolved:
                resolved.pop()
        else:
            resolved.append(item)

    curr = VFS_DATA
    for item in resolved:
        if curr.get("type") != "dir" or "children" not in curr:
            return None
        if item not in curr["children"]:
            return None
        curr = curr["children"][item]

    return curr, resolved


def cmd_ls(args: list) -> str:
    """Команда ls: вывод содержимого директории."""
    target_path = args[0] if args else "."
    res = get_node_by_path(target_path)
    if not res:
        return f"ls: невозможно получить доступ к '{target_path}': Нет файла"

    node, _ = res
    if node.get("type") == "file":
        return target_path.split("/")[-1]

    children = node.get("children", {})
    return "  ".join(children.keys())


def cmd_cd(args: list) -> str:
    """Команда cd: смена текущей директории."""
    global CURRENT_PATH
    if not args:
        CURRENT_PATH = ["/"]
        return ""

    target_path = args[0]
    res = get_node_by_path(target_path)
    if not res:
        return f"cd: {target_path}: Нет такого файла или каталога"

    node, resolved = res
    if node.get("type") != "dir":
        return f"cd: {target_path}: Не является каталогом"

    CURRENT_PATH = ["/"] + resolved
    return ""


def cmd_tac(args: list) -> str:
    """Команда tac: вывод строк файла в обратном порядке."""
    if not args:
        return "tac: пропущен операнд, задающий файл"

    res = get_node_by_path(args[0])
    if not res:
        return f"tac: {args[0]}: Нет такого файла или каталога"

    node, _ = res
    if node.get("type") != "file":
        return f"tac: {args[0]}: Это каталог"

    content = node.get("content", "")
    lines = content.splitlines()
    return "\n".join(reversed(lines))


def cmd_cal(args: list) -> str:
    """Команда cal: вывод календаря на текущий месяц."""
    now = datetime.datetime.now()
    return calendar.month(now.year, now.month)


def cmd_chown(args: list) -> str:
    """Команда chown: изменение владельца объекта в VFS."""
    if len(args) < 2:
        return "chown: пропущены аргументы (использование: chown owner file)"

    owner_spec = args[0]
    target_path = args[1]

    res = get_node_by_path(target_path)
    if not res:
        return f"chown: '{target_path}': Нет такого файла или каталога"

    node, _ = res
    parts = owner_spec.split(":")
    node["owner"] = parts[0]
    if len(parts) > 1:
        node["group"] = parts[1]

    return ""


def cmd_mv(args: list) -> str:
    """Команда mv: перемещение или переименование файла/каталога."""
    if len(args) < 2:
        return "mv: пропущен операнд"

    src_str, dst_str = args[0], args[1]
    src_res = get_node_by_path(src_str)
    if not src_res:
        return f"mv: '{src_str}': Нет такого файла или каталога"

    src_node, src_resolved = src_res
    if not src_resolved:
        return "mv: невозможно переместить корень"

    src_parent_path = "/" + "/".join(src_resolved[:-1])
    src_name = src_resolved[-1]
    src_parent_node, _ = get_node_by_path(src_parent_path)

    dst_res = get_node_by_path(dst_str)

    if dst_res and dst_res[0].get("type") == "dir":
        dst_node = dst_res[0]
        dst_node["children"][src_name] = src_node
        del src_parent_node["children"][src_name]
    else:
        dst_parts = [p for p in dst_str.split("/") if p]
        if dst_str.startswith("/"):
            dst_parent_parts = dst_parts[:-1]
            new_name = dst_parts[-1]
        else:
            current_clean = [p for p in CURRENT_PATH if p != "/"]
            all_parts = current_clean + dst_parts
            dst_parent_parts = all_parts[:-1]
            new_name = all_parts[-1]

        dst_parent_path = "/" + "/".join(dst_parent_parts)
        dst_parent_res = get_node_by_path(dst_parent_path)

        if not dst_parent_res or dst_parent_res[0].get("type") != "dir":
            return f"mv: не удалось переместить в '{dst_str}'"

        dst_parent_node = dst_parent_res[0]
        dst_parent_node["children"][new_name] = src_node
        del src_parent_node["children"][src_name]

    return ""


def cmd_conf_dump(args: list) -> str:
    """Команда conf-dump: дамп текущих настроек."""
    lines = [f"{k}={v}" for k, v in CONFIG.items()]
    return "\n".join(lines)


def execute_command(command_line: str) -> tuple[str, bool]:
    """Разбирает и выполняет команду. Возвращает (вывод, успешность)."""
    cmd_line_expanded = expand_env_vars(command_line.strip())
    if not cmd_line_expanded:
        return "", True

    tokens = cmd_line_expanded.split()
    cmd = tokens[0]
    args = tokens[1:]

    if cmd == "exit":
        sys.exit(0)
    elif cmd == "ls":
        out = cmd_ls(args)
    elif cmd == "cd":
        out = cmd_cd(args)
    elif cmd == "tac":
        out = cmd_tac(args)
    elif cmd == "cal":
        out = cmd_cal(args)
    elif cmd == "chown":
        out = cmd_chown(args)
    elif cmd == "mv":
        out = cmd_mv(args)
    elif cmd == "conf-dump":
        out = cmd_conf_dump(args)
    else:
        return f"Команда '{cmd}' не найдена", False

    if out.startswith(f"{cmd}:") or out.startswith("Команда"):
        return out, False

    return out, True


def get_prompt_text() -> str:
    """Формирует текущий пригласительный текст консоли."""
    if len(CURRENT_PATH) == 1:
        return "/ $ "
    return "/" + "/".join(CURRENT_PATH[1:]) + " $ "


def append_to_output(text_widget, text: str):
    """Добавляет текст в виджет вывода GUI."""
    text_widget.config(state="normal")
    text_widget.insert(tk.END, text)
    text_widget.see(tk.END)
    text_widget.config(state="disabled")


def run_script_file(output_widget, prompt_label):
    """Выполняет команды из стартового скрипта."""
    script_file = CONFIG["script_path"]
    if not script_file:
        return

    if not os.path.exists(script_file):
        append_to_output(
            output_widget, f"Ошибка: Скрипт '{script_file}' не найден.\n"
        )
        return

    with open(script_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            prompt = get_prompt_text()
            append_to_output(output_widget, f"{prompt}{line}\n")

            out, success = execute_command(line)
            if out:
                append_to_output(output_widget, f"{out}\n")

            prompt_label.config(text=get_prompt_text())

            if not success:
                append_to_output(
                    output_widget,
                    "\n[Ошибка] Выполнение скрипта остановлено.\n",
                )
                break


def run_gui():
    """Инициализация и запуск графического интерфейса Tkinter."""
    root = tk.Tk()
    root.title("VFS Emulator")
    root.geometry("700x450")

    output_area = scrolledtext.ScrolledText(
        root, wrap=tk.WORD, state="disabled", bg="black", fg="white"
    )
    output_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    entry_frame = tk.Frame(root)
    entry_frame.pack(fill=tk.X, padx=5, pady=5)

    prompt_label = tk.Label(entry_frame, text=get_prompt_text())
    prompt_label.pack(side=tk.LEFT)

    entry = tk.Entry(entry_frame)
    entry.pack(fill=tk.X, expand=True, side=tk.LEFT)

    def on_enter(event=None):
        cmd_str = entry.get()
        entry.delete(0, tk.END)

        prompt = get_prompt_text()
        append_to_output(output_area, f"{prompt}{cmd_str}\n")

        output, success = execute_command(cmd_str)
        if output:
            append_to_output(output_area, f"{output}\n")

        prompt_label.config(text=get_prompt_text())

    entry.bind("<Return>", on_enter)

    run_script_file(output_area, prompt_label)

    root.mainloop()


def main():
    """Точка входа в программу."""
    parse_args()
    load_vfs(CONFIG["vfs_path"])
    run_gui()


if __name__ == "__main__":
    main()