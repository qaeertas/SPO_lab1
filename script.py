import re
import math
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from collections import Counter
from typing import Tuple

def get_script_dir():
    return os.path.dirname(os.path.abspath(__file__))

KEYWORDS_NON_OPERAND = {
    'let', 'const', 'var', 'function', 'return', 'if', 'else', 'for',
    'while', 'do', 'switch', 'case', 'default', 'break', 'continue',
    'new', 'delete', 'typeof', 'instanceof', 'in', 'of', 'void', 'this',
    'class', 'extends', 'implements', 'interface', 'type', 'enum',
    'public', 'private', 'protected', 'readonly', 'static', 'abstract',
    'import', 'export', 'from', 'as', 'async', 'await',
    'yield', 'try', 'catch', 'finally', 'throw', 'null', 'undefined',
    'true', 'false', 'boolean', 'number', 'string', 'any',
}

def strip_comments(code: str) -> str:
    code = re.sub(r'/\*.*?\*/', ' ', code, flags=re.DOTALL)
    code = re.sub(r'//[^\n]*', ' ', code)
    return code

def strip_strings(code: str) -> Tuple[str, Counter]:
    operands = Counter()
    pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`'
    strs = re.findall(pattern, code)
    for _ in strs:
        operands['STR'] += 1
    code = re.sub(pattern, ' STR ', code)
    return code, operands

def parse_typescript_fixed(code: str) -> Tuple[Counter, Counter]:
    code = strip_comments(code)
    code, str_operands = strip_strings(code)
    operators = Counter()
    operands = Counter()
    operands.update(str_operands)

    for kw, op_name in [(r'\bif\b','if'),(r'\bfor\b','for'),(r'\bwhile\b','while'),(r'\breturn\b','return'),(r'\bfunction\b','function')]:
        cnt = len(re.findall(kw, code))
        if cnt:
            operators[op_name] += cnt
    dos = len(re.findall(r'\bdo\b', code))
    if dos:
        operators['do…while'] = dos

    exec_code = code
    keywords_for_calls = {'if','for','while','switch','catch','function','return'}
    i = 0
    while i < len(exec_code):
        m = re.search(r'\b((?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*)\s*\(', exec_code[i:])
        if not m:
            break
        full_name = m.group(1)
        last = full_name.split('.')[-1]
        if last in keywords_for_calls:
            i += m.end()
            continue
        paren_open = exec_code.find('(', i + m.start())
        depth = 0
        j = paren_open
        while j < len(exec_code):
            if exec_code[j] == '(':
                depth += 1
            elif exec_code[j] == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth != 0:
            i = paren_open + 1
            continue
        inner = exec_code[paren_open+1:j]
        operators[f"{full_name}()"] += 1
        for num in re.findall(r'\b\d+\b', inner):
            operands[num] += 1
        for idm in re.findall(r'\b[A-Za-z_]\w*\b', inner):
            if idm in KEYWORDS_NON_OPERAND or idm == 'STR':
                continue
            operands[idm] += 1
        exec_code = exec_code[:i+m.start()] + ' '*(j - (i+m.start()) +1) + exec_code[j+1:]
        i = i + m.start() + 1

    stack = []
    brace_pairs = 0
    for ch in exec_code:
        if ch == '{':
            stack.append(ch)
        elif ch == '}':
            if stack:
                stack.pop()
                brace_pairs += 1
    if brace_pairs:
        operators['{ }'] = brace_pairs

    stack = []
    paren_pairs = 0
    for ch in exec_code:
        if ch == '(':
            stack.append(ch)
        elif ch == ')':
            if stack:
                stack.pop()
                paren_pairs += 1
    if paren_pairs:
        operators['( )'] = paren_pairs

    simple_ops = [
        (r'===','==='),(r'!==','!=='),(r'<=','<='),(r'>=','>='),(r'==','=='),(r'!=','!='),
        (r'\+\+','++'),(r'--','--'),(r'\+=','+='),(r'-=','-='),(r'\*=','*='),(r'/=','/='),
        (r'&&','&&'),(r'\|\|','||'),(r'=>','=>'),
        (r'\+','+'),(r'-','-'),(r'\*','*'),(r'/', '/'),(r'%', '%'),
        (r'<','<'),(r'>','>'),(r'=','='),(r':',':'),(r';',';'),(r',',','),(r'\.', '.'),
    ]
    for pat, name in simple_ops:
        matches = re.findall(pat, exec_code)
        if matches:
            operators[name] += len(matches)
            exec_code = re.sub(pat, ' ', exec_code)

    for idm in re.findall(r'\b[A-Za-z_]\w*\b', exec_code):
        if idm in KEYWORDS_NON_OPERAND or idm == 'STR':
            continue
        operands[idm] += 1
    for num in re.findall(r'\b\d+\b', exec_code):
        operands[num] += 1

    return operators, operands

def calculate_metrics(op_counts, operand_counts):
    eta1 = len(op_counts)
    eta2 = len(operand_counts)
    N1 = sum(op_counts.values())
    N2 = sum(operand_counts.values())
    eta = eta1 + eta2
    N = N1 + N2
    V = N * math.log2(eta) if eta > 1 else 0.0
    return dict(eta1=eta1, eta2=eta2, N1=N1, N2=N2, eta=eta, N=N, V=V, op_counts=op_counts, operand_counts=operand_counts)

class HalsteadAppFixed:
    def __init__(self, root):
        self.root = root
        root.title("Метрики Холстеда — TypeScript (Fixed Windows Path)")
        root.geometry("1250x800")
        top = ttk.Frame(root, padding=5); top.pack(fill=tk.X)
        ttk.Button(top, text="Открыть файл…", command=self.open_file).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Анализировать", command=self.analyze).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Загрузить из папки скрипта", command=self.load_90).pack(side=tk.LEFT, padx=4)
        main = ttk.Frame(root); main.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        left = ttk.LabelFrame(main, text="Исходный код TypeScript (90-100 строк)")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.code_text = scrolledtext.ScrolledText(left, wrap=tk.NONE, font=("Consolas", 10))
        self.code_text.pack(fill=tk.BOTH, expand=True)
        right = ttk.LabelFrame(main, text="Результаты")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        nb = ttk.Notebook(right); nb.pack(fill=tk.BOTH, expand=True)
        tab1 = ttk.Frame(nb); nb.add(tab1, text="Базовые метрики")
        self._build_base_tab(tab1)
        tab2 = ttk.Frame(nb); nb.add(tab2, text="Расширенные метрики")
        self._build_ext_tab(tab2)
        self.status = ttk.Label(root, text="Готов", relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)
        self.load_90()

    def _build_base_tab(self, parent):
        wrap = ttk.Frame(parent); wrap.pack(fill=tk.BOTH, expand=True)
        op_f = ttk.LabelFrame(wrap, text="Операторы")
        op_f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.op_tree = ttk.Treeview(op_f, columns=("j","op","f"), show="headings", height=25)
        for c,t,w,a in [("j","j",40,"center"),("op","Оператор",180,"w"),("f","f₁ⱼ",70,"center")]:
            self.op_tree.heading(c, text=t); self.op_tree.column(c, width=w, anchor=a)
        self.op_tree.pack(fill=tk.BOTH, expand=True)
        od_f = ttk.LabelFrame(wrap, text="Операнды")
        od_f.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.od_tree = ttk.Treeview(od_f, columns=("i","op","f"), show="headings", height=25)
        for c,t,w,a in [("i","i",40,"center"),("op","Операнд",180,"w"),("f","f₂ᵢ",70,"center")]:
            self.od_tree.heading(c, text=t); self.od_tree.column(c, width=w, anchor=a)
        self.od_tree.pack(fill=tk.BOTH, expand=True)
        self.base_summary = ttk.Label(parent, text="", justify=tk.LEFT, font=("Consolas", 10))
        self.base_summary.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=6)

    def _build_ext_tab(self, parent):
        self.ext_tree = ttk.Treeview(parent, columns=("name","formula","value"), show="headings", height=10)
        for c,t,w,a in [("name","Метрика",250,"w"),("formula","Формула",250,"w"),("value","Значение",150,"center")]:
            self.ext_tree.heading(c, text=t); self.ext_tree.column(c, width=w, anchor=a)
        self.ext_tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("TypeScript","*.ts"),("JavaScript","*.js"),("All","*.*")])
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            except:
                with open(path, "r", encoding="cp1251") as f:
                    content = f.read()
            self.code_text.delete("1.0", tk.END)
            self.code_text.insert("1.0", content)
            self.status.config(text=f"Загружено: {path} ({len(content.splitlines())} строк)")

    def load_90(self):
        script_dir = get_script_dir()
        candidates = ["sample_90_lines.ts","program.ts","code.ts","input.ts","test.ts"]
        found_path = None
        for name in candidates:
            p = os.path.join(script_dir, name)
            if os.path.exists(p):
                found_path = p
                break
        if not found_path:
            for file in os.listdir(script_dir):
                if file.endswith('.ts') or file.endswith('.js'):
                    if 'halstead' in file.lower() or 'parser' in file.lower():
                        continue
                    found_path = os.path.join(script_dir, file)
                    break
        if found_path and os.path.exists(found_path):
            try:
                with open(found_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except:
                with open(found_path, "r", encoding="cp1251") as f:
                    content = f.read()
            self.code_text.delete("1.0", tk.END)
            self.code_text.insert("1.0", content)
            self.status.config(text=f"Загружено из папки скрипта: {found_path} — {len(content.splitlines())} строк")
        else:
            messagebox.showinfo("Файл не найден", f"Положи .ts файл в папку:\n{script_dir}")

    def clear_all(self):
        self.code_text.delete("1.0", tk.END)
        for tr in (self.op_tree, self.od_tree, self.ext_tree):
            for it in tr.get_children():
                tr.delete(it)
        self.base_summary.config(text="")

    def analyze(self):
        code = self.code_text.get("1.0", tk.END)
        if not code.strip():
            messagebox.showwarning("Пусто","Введите код")
            return
        op_c, od_c = parse_typescript_fixed(code)
        m = calculate_metrics(op_c, od_c)
        for tr in (self.op_tree, self.od_tree):
            for it in tr.get_children():
                tr.delete(it)
        for j, (op, f) in enumerate(sorted(m['op_counts'].items(), key=lambda kv: (-kv[1], kv[0])), 1):
            self.op_tree.insert("", tk.END, values=(j, op, f))
        for i, (op, f) in enumerate(sorted(m['operand_counts'].items(), key=lambda kv: (-kv[1], kv[0])), 1):
            self.od_tree.insert("", tk.END, values=(i, op, f))
        self.base_summary.config(text=f"η₁={m['eta1']} N₁={m['N1']}   η₂={m['eta2']} N₂={m['N2']}   Строк: {len(code.splitlines())}")
        for it in self.ext_tree.get_children():
            self.ext_tree.delete(it)
        self.ext_tree.insert("", tk.END, values=("Число уникальных операторов, η₁","η₁ = |{операторы}|",f"{m['eta1']}"))
        self.ext_tree.insert("", tk.END, values=("Число уникальных операндов, η₂","η₂ = |{операнды}|",f"{m['eta2']}"))
        self.ext_tree.insert("", tk.END, values=("Общее число операторов, N₁","N₁ = Σf₁ⱼ",f"{m['N1']}"))
        self.ext_tree.insert("", tk.END, values=("Общее число операндов, N₂","N₂ = Σf₂ᵢ",f"{m['N2']}"))
        self.ext_tree.insert("", tk.END, values=("Словарь программы, η","η = η₁ + η₂",f"{m['eta']}"))
        self.ext_tree.insert("", tk.END, values=("Длина программы, N","N = N₁ + N₂",f"{m['N']}"))
        self.ext_tree.insert("", tk.END, values=("Объём программы, V","V = N · log₂ η",f"{m['V']:.2f} бит"))

if __name__ == "__main__":
    root = tk.Tk()
    HalsteadAppFixed(root)
    root.mainloop()
