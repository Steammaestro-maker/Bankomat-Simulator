#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ATM simulator — улучшенная версия:
- Главный экран: 1) регистрация 2) просмотр/выбор карт 0) выход
- Регистрация: ввод имени/фамилии -> генерация номера/expiry/CVV -> установка PIN -> сохранение
- Просмотр карт: список, выбор по индексу -> ввод PIN -> сессия карты
- В сессии: 1..6 действия (баланс, пополнение, снятие, история, смена PIN, данные)
- Каждое действие подтверждается (д/н). После выхода с карты при повторном входе требуется PIN.
- Данные карт хранятся в cards.json
"""

from __future__ import annotations

import json
import os
import random
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from getpass import getpass
from typing import Dict, List, Optional, Tuple

DATA_FILE = "cards.json"
MAX_PIN_ATTEMPTS = 3
CURRENCY = "сом"


@dataclass
class Card:
    first_name: str
    last_name: str
    pin: str
    number: str
    expiry: Optional[str] = None
    cvv: Optional[str] = None

    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class ATM:
    def __init__(self, card: Card, balance: int = 0, transactions: Optional[List[Tuple[str, int]]] = None) -> None:
        self.card = card
        self._balance = int(balance)
        self.is_authenticated = False
        self._transactions: List[Tuple[str, int]] = transactions or []

    @property
    def balance(self) -> int:
        return self._balance

    def authenticate(self, entered_pin: str) -> bool:
        if str(entered_pin) == str(self.card.pin):
            self.is_authenticated = True
            return True
        return False

    def get_balance(self) -> str:
        return f"Ваш текущий баланс: {self._balance} {CURRENCY}"

    def deposit(self, amount: int) -> str:
        if amount <= 0:
            return "Сумма пополнения должна быть больше нуля."
        self._balance += amount
        self._transactions.append(("Пополнение", amount))
        return f"Счет пополнен на {amount} {CURRENCY}. Новый баланс: {self._balance} {CURRENCY}"

    def withdraw(self, amount: int) -> str:
        if amount <= 0:
            return "Введите корректную сумму (больше нуля)."
        if amount > self._balance:
            return "Недостаточно средств на счету."
        self._balance -= amount
        self._transactions.append(("Снятие", amount))
        return f"Вы сняли {amount} {CURRENCY}. Остаток: {self._balance} {CURRENCY}"

    def change_pin(self, old_pin: str, new_pin: str) -> str:
        if str(old_pin) != str(self.card.pin):
            return "Старый PIN неверный."
        if not (new_pin.isdigit() and 4 <= len(new_pin) <= 6):
            return "Новый PIN должен состоять из 4-6 цифр."
        self.card.pin = new_pin
        return "PIN успешно изменён."

    def get_transactions(self) -> List[Tuple[str, int]]:
        return list(self._transactions)


# ---------- Persistence helpers ----------

def load_data(path: str = DATA_FILE) -> Dict:
    if not os.path.exists(path):
        return {"cards": []}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"cards": []}


def save_data(data: Dict, path: str = DATA_FILE) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def generate_card_number(existing_numbers: Optional[List[str]] = None) -> str:
    existing_numbers = existing_numbers or []
    while True:
        number = str(random.randint(10**15, 10**16 - 1))
        if number not in existing_numbers:
            return number


def generate_expiry(min_years_ahead: int = 2, max_years_ahead: int = 7) -> str:
    """
    Сгенерировать срок действия MM/YY, где год >= текущий год + min_years_ahead.
    По умолчанию диапазон: now+2 .. now+7 лет.
    """
    now = datetime.now()
    min_year_full = now.year + min_years_ahead
    max_year_full = now.year + max_years_ahead
    year_full = random.randint(min_year_full, max_year_full)
    year = year_full % 100
    month = random.randint(1, 12)
    return f"{month:02d}/{year:02d}"


def generate_cvv() -> str:
    return f"{random.randint(0, 999):03d}"


def create_card_record(first: str, last: str, pin: str, number: str, expiry: str, cvv: str, initial_balance: int = 10000, data_path: str = DATA_FILE) -> Dict:
    data = load_data(data_path)
    record = {
        "number": number,
        "first_name": first.strip(),
        "last_name": last.strip(),
        "pin": str(pin),
        "expiry": expiry,
        "cvv": cvv,
        "balance": int(initial_balance),
        "transactions": [],
    }
    data.setdefault("cards", []).append(record)
    save_data(data, data_path)
    return record


def find_card_record(number: str, data_path: str = DATA_FILE) -> Optional[Dict]:
    data = load_data(data_path)
    for rec in data.get("cards", []):
        if rec.get("number") == number:
            return rec
    return None


def update_card_record(rec: Dict, data_path: str = DATA_FILE) -> None:
    data = load_data(data_path)
    for i, r in enumerate(data.get("cards", [])):
        if r.get("number") == rec.get("number"):
            data["cards"][i] = rec
            save_data(data, data_path)
            return
    data.setdefault("cards", []).append(rec)
    save_data(data, data_path)


# ---------- Interactive helpers ----------

def prompt_int(prompt: str) -> int:
    while True:
        try:
            raw = input(prompt).strip()
            if raw.lower() in ("отмена", "cancel", "c"):
                raise KeyboardInterrupt
            value = int(raw)
            return value
        except ValueError:
            print("Ошибка: введите целое число. Введите 'отмена' чтобы вернуться.")
        except KeyboardInterrupt:
            raise


def valid_name_part(s: str) -> bool:
    s = s.strip()
    return bool(s) and any(ch.isalpha() for ch in s)


def normalize_name(s: str) -> str:
    return s.strip().title()


def prompt_yes_no(prompt: str) -> bool:
    yes = {"д", "да", "y", "yes"}
    no = {"н", "нет", "n", "no"}
    while True:
        resp = input(prompt).strip().lower()
        if resp in yes:
            return True
        if resp in no:
            return False
        print("Пожалуйста, введите 'д' (да) или 'н' (нет).")


def show_help() -> None:
    print("\nСправка — команды и подсказки:")
    print("Главное меню:")
    print("  1 — Зарегистрировать новую карту")
    print("  2 — Просмотр зарегистрированных карт")
    print("  help — Справка")
    print("  0 — Выйти")
    print("В сессии карты:")
    print("  1 — Просмотреть баланс")
    print("  2 — Пополнить счёт")
    print("  3 — Снять наличные")
    print("  4 — История транзакций")
    print("  5 — Сменить PIN")
    print("  6 — Показать данные карты")
    print("  help — Справка")
    print("  0 — Выход из сессии")
    print("Примечания:")
    print(" - Подтверждения: введите 'д' или 'н' (регистр не важен).")
    print(" - При вводе сумм можно ввести 'отмена' для возврата в меню.")
    print(" - Имя и фамилия автоматически нормализуются (Title case).\n")


def mask_card_number(number: str) -> str:
    if len(number) >= 8:
        return f"{number[:4]} {'*'*4} {number[-4:]}"
    return number


def list_cards(data_path: str = DATA_FILE) -> List[Dict]:
    data = load_data(data_path)
    return data.get("cards", [])


def read_pin(prompt: str) -> str:
    """
    Надёжный ввод PIN:
    - если stdin — TTY: используем getpass (скрытый ввод);
    - если не TTY (IDE/debugger): используем input и предупреждаем пользователя;
    - обрабатываем EOF/Ctrl-C и слова отмены ('отмена','cancel','c');
    - возвращаем пустую строку при отмене/ошибке.
    """
    try:
        if sys.stdin.isatty():
            pin = getpass(prompt)
        else:
            print("Внимание: в этой среде ввод PIN будет видим.")
            pin = input(prompt)
    except (EOFError, KeyboardInterrupt):
        print("\nВвод PIN прерван. Возврат в меню.")
        return ""

    if pin is None:
        pin = ""
    pin = pin.strip()
    if not pin:
        print("(PIN не введён) Возврат в меню.")
        return ""
    if pin.lower() in ("отмена", "cancel", "c"):
        print("Операция отменена пользователем.")
        return ""
    print("(PIN введён)")
    return pin


# ---------- Registration and selection ----------

def register_card_interactive(data_path: str = DATA_FILE) -> Dict:
    try:
        print("Регистрация новой карты:")
        while True:
            first = input("Введите имя: ").strip()
            if not valid_name_part(first):
                print("Имя не должно быть пустым и должно содержать буквы.")
                continue
            first = normalize_name(first)
            break

        while True:
            last = input("Введите фамилию: ").strip()
            if not valid_name_part(last):
                print("Фамилия не должна быть пустой и должна содержать буквы.")
                continue
            last = normalize_name(last)
            break

        data = load_data(data_path)
        existing = [c["number"] for c in data.get("cards", [])]
        number = generate_card_number(existing)
        expiry = generate_expiry()
        cvv = generate_cvv()

        print("\nСгенерированы данные карты:")
        print(f"  Номер карты: {number}")
        print(f"  Срок действия: {expiry}")
        print(f"  CVV: {cvv}")
        print("Теперь задайте PIN для этой карты (4-6 цифр).")

        while True:
            pin1 = read_pin("Задайте PIN (4-6 цифр): ")
            if not pin1:
                print("Регистрация отменена пользователем.")
                return {}
            pin2 = read_pin("Повторите PIN: ")
            if not pin2:
                print("Регистрация отменена пользователем.")
                return {}

            if pin1 != pin2:
                print("PINы не совпадают. Попробуйте снова.")
                continue
            if not (pin1.isdigit() and 4 <= len(pin1) <= 6):
                print("PIN должен состоять из 4-6 цифр.")
                continue
            break

        print(f"Подтвердите регистрацию карты для {first} {last} (д/н):")
        if not prompt_yes_no("Ваш выбор (д/н): "):
            print("Регистрация отменена.")
            return {}

        rec = create_card_record(first, last, pin1, number=number, expiry=expiry, cvv=cvv, initial_balance=10000, data_path=data_path)
        print(f"\nКарта зарегистрирована: {rec.get('first_name')} {rec.get('last_name')} — {mask_card_number(rec.get('number'))}, срок {rec.get('expiry')}")
        if prompt_yes_no("Открыть меню для этой карты сейчас? (д/н): "):
            atm = ATM(Card(rec['first_name'], rec['last_name'], rec['pin'], rec['number'], rec.get('expiry'), rec.get('cvv')), balance=rec.get('balance', 0), transactions=rec.get('transactions', []))
            atm.is_authenticated = True
            session_loop(rec, atm, data_path)
        return rec

    except KeyboardInterrupt:
        print("\nРегистрация прервана пользователем. Возврат в главное меню.")
        return {}


def select_card_and_auth(data_path: str = DATA_FILE) -> Optional[Tuple[Dict, ATM]]:
    cards = list_cards(data_path)
    if not cards:
        print("Нет зарегистрированных карт.")
        return None

    print("\nЗарегистрированные карты:")
    for i, c in enumerate(cards, start=1):
        print(f"{i}. {c.get('first_name')} {c.get('last_name')} — {mask_card_number(c.get('number'))} (срок {c.get('expiry')})")

    while True:
        try:
            idx = int(input("Выберите карту по номеру (0 — назад): ").strip())
        except ValueError:
            print("Введите номер карты (целое число).")
            continue
        if idx == 0:
            return None
        if 1 <= idx <= len(cards):
            rec = cards[idx - 1]
            break
        print("Неверный номер. Попробуйте снова.")

    attempts = 0
    atm = ATM(Card(rec['first_name'], rec['last_name'], rec['pin'], rec['number'], rec.get('expiry'), rec.get('cvv')), balance=rec.get('balance', 0), transactions=rec.get('transactions', []))
    while attempts < MAX_PIN_ATTEMPTS and not atm.is_authenticated:
        entered = read_pin("Введите PIN для выбранной карты: ")
        if not entered:
            print("Аутентификация отменена. Возврат в главное меню.")
            return None
        if atm.authenticate(entered):
            print(f"PIN верный. Добро пожаловать, {atm.card.first_name}!\n")
            return rec, atm
        attempts += 1
        print(f"Неверный PIN. Осталось попыток: {MAX_PIN_ATTEMPTS - attempts}")
    print("Превышено количество попыток. Возврат в главное меню.")
    return None


# ---------- Menus and session ----------

def print_main_menu() -> None:
    print("\n" + "=" * 40)
    print("Главное меню:")
    print("1. Зарегистрировать новую карту")
    print("2. Просмотреть зарегистрированные карты")
    print("help. Справка")
    print("0. Выйти")
    print("=" * 40)


def print_session_menu() -> None:
    print("\n" + "=" * 40)
    print("Меню карты:")
    print("1. Просмотреть баланс")
    print("2. Пополнить счёт")
    print("3. Снять наличные")
    print("4. История транзакций")
    print("5. Сменить PIN")
    print("6. Показать данные карты")
    print("help. Справка")
    print("0. Выйти из сессии")
    print("=" * 40)


def session_loop(rec: Dict, atm: ATM, data_path: str = DATA_FILE) -> None:
    while True:
        print_session_menu()
        cmd = input("Введите номер действия (0-6) или 'help': ").strip().lower()
        if cmd == "1":
            if not prompt_yes_no("Подтвердите: Просмотреть баланс? (д/н): "):
                continue
            print(atm.get_balance())
        elif cmd == "2":
            if not prompt_yes_no("Подтвердите: ��ополнить счёт? (д/н): "):
                continue
            try:
                amount = prompt_int("Введите сумму для пополнения (целое число): ")
            except KeyboardInterrupt:
                print("Отмена операции. Возврат в меню.")
                continue
            print(atm.deposit(amount))
            rec["balance"] = atm.balance
            rec["transactions"] = atm.get_transactions()
            update_card_record(rec, data_path)
        elif cmd == "3":
            if not prompt_yes_no("Подтвердите: Снять наличные? (д/н): "):
                continue
            try:
                amount = prompt_int("Введите сумму для снятия (целое число): ")
            except KeyboardInterrupt:
                print("Отмена операции. Возврат в меню.")
                continue
            print(atm.withdraw(amount))
            rec["balance"] = atm.balance
            rec["transactions"] = atm.get_transactions()
            update_card_record(rec, data_path)
        elif cmd == "4":
            if not prompt_yes_no("Подтвердите: Посмотреть историю транзакций? (д/н): "):
                continue
            txs = atm.get_transactions()
            if not txs:
                print("Транзакций пока нет.")
            else:
                print("История транзакций:")
                for i, (t_type, amt) in enumerate(txs, start=1):
                    print(f"{i}. {t_type}: {amt} {CURRENCY}")
        elif cmd == "5":
            if not prompt_yes_no("Подтвердите: Сменить PIN? (д/н): "):
                continue
            old = read_pin("Введите текущий PIN: ")
            if not old:
                print("Операция смены PIN отменена.")
                continue
            new = input("Введите новый PIN (4-6 цифр): ").strip()
            msg = atm.change_pin(old, new)
            print(msg)
            rec["pin"] = atm.card.pin
            rec["balance"] = atm.balance
            rec["transactions"] = atm.get_transactions()
            update_card_record(rec, data_path)
        elif cmd == "6":
            if not prompt_yes_no("Подтвердите: Показать данные карты? (д/н): "):
                continue
            print(f"Данные карты: Владелец: {atm.card.full_name()}, Номер: {atm.card.number}, Срок: {atm.card.expiry}, CVV: {atm.card.cvv}")
        elif cmd == "help":
            show_help()
        elif cmd == "0":
            print("Выход из сессии пользователя.")
            break
        else:
            print("Некорректный ввод. Введите номер пункта меню (0-6) или 'help'.")


def run_atm_simulation(data_path: str = DATA_FILE) -> None:
    print("Добро пожаловать в симулятор банкомата.")
    while True:
        print_main_menu()
        choice = input("Выберите действие (0-2/help): ").strip().lower()
        if choice == "1":
            _ = register_card_interactive(data_path)
            continue
        elif choice == "2":
            sel = select_card_and_auth(data_path)
            if not sel:
                continue
            rec, atm = sel
            session_loop(rec, atm, data_path)
            continue
        elif choice == "help":
            show_help()
            continue
        elif choice == "0":
            if prompt_yes_no("Подтвердите выход из программы (д/н): "):
                print("Спасибо за использование симулятора. До свидания!")
                break
            else:
                print("Выход отменён. Возврат в главное меню.")
                continue
        else:
            print("Некорректный выбор. Введите 0, 1, 2 или 'help'.")


if __name__ == "__main__":
    try:
        run_atm_simulation()
    except KeyboardInterrupt:
        print("\nПрограмма прервана пользователем. Выход.")
        sys.exit(0)
    except Exception:
        print("Произошла непредвиденная ошибка, подробности:")
        traceback.print_exc()
        sys.exit(1)

# End of atm_simulator.py
