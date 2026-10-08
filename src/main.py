import argparse
import calendar
import datetime
import json
import os
import sys
import tkinter as tk
from tkinter import scrolledtext

DEFAULT_WINDOW_WIDTH = 700
DEFAULT_WINDOW_HEIGHT = 450
MIN_ARGS_COUNT_CHOWN = 2

CONFIG = {
    "vfs_path": "",
    "script_path": "",
}

vfs_data = {}
current_path = ["/"]


def parse_args():
    parser = argparse.ArgumentParser(description="VFS Emulator")
    parser.add_argument("--vfs-path", "-v", type=str, default="")
    parser.add_argument("--script-path", "-s", type=str, default="")
    args = parser.parse_args()
    CONFIG["vfs_path"] = args.vfs_path
    CONFIG["script_path"] = args.script_path


def load_vfs(path: str):
    global vfs_data
    if not path:
        vfs_data = {"type": "dir", "name": "/", "children": {}}
        return

    if not os.path.exists(path):
        print(f"Ошибка: Файл VFS '{path}' не найден.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(path, "r", encoding="utf-8") as f:
            vfs_data = json.load(f)
    except Exception as err:
        print(f"Ошибка чтения VFS JSON: {err}", file=sys.stderr)
        sys.exit(1)


def resolve_path_parts(path_str: str) -> list:
    parts = []
    if not path_str.startswith("/"):
        parts.extend(p for p in current_path if p != "/")
    parts.extend(p for p in path_str.split("/") if p)

    resolved = []
    for item in parts:
        if item == "..":
            if resolved:
                resolved.pop()
        elif item != ".":
            resolved.append(item)
    return resolved


def get_node_by_path(path_str: str):
    resolved = resolve_path_parts(path_str)
    curr = vfs_data
    for item in resolved:
        if curr.get("type") != "dir" or "children" not in curr:
            return None
        if item not in curr["children"]:
            return None
        curr = curr["children"][item]
    return curr, resolved


def cmd_ls(args: list) -> str:
    target_path = args[0] if args else "."
    res = get_node_by_path(target_path)
    if not res:
        err = f"ls: нет доступа к '{target_path}': Нет файла"
        return err

    node, _ = res
    if node.get("type") == "file":
        return target_path.split("/")[-1]

    children = node.get("children", {})
    return "  ".join(children.keys())


def cmd_cd(args: list) -> str:
    global current_path
    if not args:
        current_path = ["/"]
        return ""

    target_path = args[0]
    res = get_node_by_path(target_path)
    if not res:
        return f"cd: {target_path}: Нет такого файла или каталога"

    node, resolved = res
    if node.get("type") != "dir":
        return f"cd: {target_path}: Не является каталогом"

    current_path = ["/"] + resolved
    return ""


def cmd_tac(args: list) -> str:
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
    now = datetime.datetime.now()
    return calendar.month(now.year, now.month)


def cmd_chown(args: list) -> str:
    if len(args) < MIN_ARGS_COUNT_CHOWN:
        return "chown: пропущены аргументы"

    owner_spec, target_path = args[0], args[1]
    res = get_node_by_path(target_path)
    if not res:
        return f"chown: '{target_path}': Нет такого файла"

    node, _ = res
    parts = owner_spec.split(":")
    node["owner"] = parts[0]
    if len(parts) > 1:
        node["group"] = parts[1]

    return ""


def get_parent_node_and_name(path_str: str):
    parts = resolve_path_parts(path_str)
    if not parts:
        return None, ""
    name = parts[-1]
    parent_path = "/" + "/".join(parts[:-1]) if len(parts) > 1 else "/"
    res = get_node_by_path(parent_path)
    if not res:
        return None, name
    return res[0], name


def cmd_mv(args: list) -> str:
    if len(args) < MIN_ARGS_COUNT_CHOWN:
        return "mv: пропущены аргументы"

    src_path, dst_path = args[0], args[1]
    src_res = get_node_by_path(src_path)
    if not src_res:
        return f"mv: ошибка stat для '{src_path}': Нет файла"

    src_node, _ = src_res
    src_parent, src_name = get_parent_node_and_name(src_path)
    dst_res = get_node_by_path(dst_path)

    if dst_res and dst_res[0].get("type") == "dir":
        dst_res[0]["children"][src_name] = src_node
    else:
        dst_parent, dst_name = get_parent_node_and_name(dst_path)
        if not dst_parent:
            return "mv: не удалось переместить"
        dst_parent["children"][dst_name] = src_node

    if (src_parent and "children" in src_parent
            and src_name in src_parent["children"]):
        del src_parent["children"][src_name]

    return ""


def cmd_conf_dump(args: list) -> str:
    vfs_p = CONFIG["vfs_path"]
    script_p = CONFIG["script_path"]
    return f"vfs_path: {vfs_p}\nscript_path: {script_p}"


def execute_command(line: str) -> str:
    parts = line.strip().split()
    if not parts:
        return ""

    cmd = parts[0]
    args = parts[1:]

    commands = {
        "ls": cmd_ls,
        "cd": cmd_cd,
        "tac": cmd_tac,
        "cal": cmd_cal,
        "chown": cmd_chown,
        "mv": cmd_mv,
        "conf-dump": cmd_conf_dump,
    }

    if cmd in commands:
        return commands[cmd](args)
    if cmd == "exit":
        sys.exit(0)
    return f"{cmd}: команда не найдена"


def get_prompt() -> str:
    path_str = "/".join(current_path).replace("//", "/")
    return f"{path_str} $ "


def _execute_startup_script(append_out, prompt_lbl):
    script = CONFIG["script_path"]
    if script and os.path.exists(script):
        with open(script, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    append_out(f"{get_prompt()}{line}")
                    out = execute_command(line)
                    if out:
                        append_out(out)
                    prompt_lbl.config(text=get_prompt())


def run_gui():
    root = tk.Tk()
    root.title("VFS Emulator")
    root.geometry(f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}")

    output_area = scrolledtext.ScrolledText(
        root, wrap=tk.WORD, state="disabled", bg="black", fg="white"
    )
    output_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    entry_frame = tk.Frame(root)
    entry_frame.pack(fill=tk.X, padx=5, pady=5)

    prompt_label = tk.Label(entry_frame, text=get_prompt())
    prompt_label.pack(side=tk.LEFT)

    entry = tk.Entry(entry_frame)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def append_output(text: str):
        output_area.config(state="normal")
        output_area.insert(tk.END, text + "\n")
        output_area.config(state="disabled")
        output_area.see(tk.END)

    def on_submit(event=None):
        cmd_text = entry.get()
        entry.delete(0, tk.END)
        append_output(f"{get_prompt()}{cmd_text}")
        if cmd_text.strip():
            out = execute_command(cmd_text)
            if out:
                append_output(out)
        prompt_label.config(text=get_prompt())

    entry.bind("<Return>", on_submit)
    _execute_startup_script(append_output, prompt_label)
    root.mainloop()


def main():
    parse_args()
    load_vfs(CONFIG["vfs_path"])
    run_gui()


if __name__ == "__main__":
    main()