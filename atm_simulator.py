#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ATM simulator (Консольная симуляция банкомата) с регистрацией карты и сохранением данных.

Запуск:
    python atm_simulator.py

Особенности:
- Регистрация карты: ввод имени, фамилии и установка PIN (4-6 цифр).
- Каждая карта получает уникальный номер (16 цифр) и начальный баланс 10000 сом.
- Данные карт (баланс, транзакции, PIN) сохраняются в JSON между запусками (cards.json).
- Поддержка нескольких карт: вход по номеру карты + PIN.
- Скрытый ввод PIN (getpass)
- До 3 попыток ввода PIN при аутентификации
- Меню в цикле (программа не закрывается сразу)
- Валидация ввода (try/except)
- История транзакций
- Понятный интерфейс на русском
"""

from __future__ import annotations

import json
import os
import random
import sys
from dataclasses import dataclass, asdict
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

    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

class ATM:
    """Класс, моделирующий поведение банкомата для одной карты (в памяти)."""

    def __init__(self, card: Card, balance: int = 0, transactions: Optional[List[Tuple[str, int]]] = None) -> None:
        self.card = card
        self._balance = int(balance)
        self.is_authenticated = False
        self._transactions: List[Tuple[str, int]] = transactions or []

    @property
    def balance(self) -> int:
        return self._balance

    def authenticate(self, entered_pin: str) -> bool:
        """Проверить PIN и установить флаг аутентификации."""
        if str(entered_pin) == str(self.card.pin):
            self.is_authenticated = True
            return True
        return False

    def get_balance(self) -> str:
        """Вернуть строку с текущим балансом."""
        return f"Ваш текущий баланс: {self._balance} {CURRENCY}"

    def deposit(self, amount: int) -> str:
        """Пополнить счет, вернуть сообщение о результате."""
        if amount <= 0:
            return "Сумма пополнения должна быть больше нуля."
        self._balance += amount
        self._transactions.append(("Пополнение", amount))
        return f"Счет пополнен на {amount} {CURRENCY}. Новый баланс: {self._balance} {CURRENCY}"

    def withdraw(self, amount: int) -> str:
        """Снять со счета с проверкой баланса."""
        if amount <= 0:
            return "Введите корректную сумму (больше нуля)."
        if amount > self._balance:
            return "Недостаточно средств на счету."
        self._balance -= amount
        self._transactions.append(("Снятие", amount))
        return f"Вы сняли {amount} {CURRENCY}. Остаток: {self._balance} {CURRENCY}"

    def change_pin(self, old_pin: str, new_pin: str) -> str:
        """Сменить PIN при корректном старом PIN."""
        if str(old_pin) != str(self.card.pin):
            return "Старый PIN неверный."
        if not (new_pin.isdigit() and 4 <= len(new_pin) <= 6):
            return "Новый PIN должен состоять из 4-6 цифр."
        self.card.pin = new_pin
        return "PIN успешно изменён."

    def get_transactions(self) -> List[Tuple[str, int]]:
        """Вернуть журнал транзакций (копия)."""
        return list(self._transactions)

# ---------- Persistence helpers ----------

def load_data(path: str = DATA_FILE) -> Dict:
    """Загрузить данные из JSON. Возвращает словарь с ключом 'cards' (список записей)."""
    if not os.path.exists(path):
        return {"cards": []}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        # Если файл повреждён, не падать — вернуть пустой реестр
        return {"cards": []}


def save_data(data: Dict, path: str = DATA_FILE) -> None:
    """Сохранить данные в JSON."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def generate_card_number(existing_numbers: Optional[List[str]] = None) -> str:
    """Сгенерировать уникальный 16-значный номер карты."""
    existing_numbers = existing_numbers or []
    while True:
        number = str(random.randint(10**15, 10**16 - 1))
        if number not in existing_numbers:
            return number


def create_card_record(first: str, last: str, pin: str, initial_balance: int = 10000, data_path: str = DATA_FILE) -> Dict:
    """Создать запись карты, сохранить в JSON и вернуть запись."""
    data = load_data(data_path)
    existing = [c["number"] for c in data.get("cards", [])]
    number = generate_card_number(existing)
    record = {
        "number": number,
        "first_name": first.strip(),
        "last_name": last.strip(),
        "pin": str(pin),
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
    # Если не найден — добавить
    data.setdefault("cards", []).append(rec)
    save_data(data, data_path)

# ---------- Interactive helpers ----------

def prompt_int(prompt: str) -> int:
    """Запрос целого числа с обработкой ошибок."""
    while True:
        try:
            raw = input(prompt).strip()
            if raw.lower() in ("отмена", "cancel", "c"):
                raise KeyboardInterrupt
            value = int(raw)
            return value
        except ValueError:
            print("Ошибка: введите целое число. Введите 'отмена' чтобы вернуться в меню.")
        except KeyboardInterrupt:
            raise


def valid_name_part(s: str) -> bool:
    """Простейшая проверка на имя/фамилию (не пусто и содержит буквы)."""
    s = s.strip()
    return bool(s) and any(ch.isalpha() for ch in s)


def register_card_interactive(data_path: str = DATA_FILE) -> Dict:
    """Процесс регистрации карты: ввод имени, фамилии и PIN; создаётся запись и сохраняется."""
    print("Регистрация новой карты:")
    while True:
        first = input("Введите имя: ").strip()
        if not valid_name_part(first):
            print("Имя не должно быть пустым и должно содержать буквы.")
            continue
        break

    while True:
        last = input("Введите фамилию: ").strip()
        if not valid_name_part(last):
            print("Фамилия не должна быть пустой и должна содержать буквы.")
            continue
        break

    # Установка PIN (повтор подтверждения)
    while True:
        try:
            pin1 = getpass("Задайте PIN (4-6 цифр): ").strip()
        except Exception:
            pin1 = input("Задайте PIN (4-6 цифр): ").strip()
        try:
            pin2 = getpass("Повторите PIN: ").strip()
        except Exception:
            pin2 = input("Повторите PIN: ").strip()

        if pin1 != pin2:
            print("PINы не совпадают. Попробуйте снова.")
            continue
        if not (pin1.isdigit() and 4 <= len(pin1) <= 6):
            print("PIN должен состоять из 4-6 цифр.")
            continue
        break

    rec = create_card_record(first, last, pin1, initial_balance=10000, data_path=data_path)
    print(f"Карта зарегистрирована для {rec.get('first_name')} {rec.get('last_name')}. Номер карты: {rec.get('number')}. Начальный баланс: {rec.get('balance')} {CURRENCY}")
    return rec


def authenticate_card_interactive(data_path: str = DATA_FILE) -> Optional[Tuple[Dict, ATM]]:
    """Аутентификация: ввод номера карты и PIN, возвращает (record, ATM) или None."""
    data = load_data(data_path)
    if not data.get("cards"):
        print("Нет зарегистрированных карт. Зарегистрируйте карту сначала.")
        return None

    number = input("Введите номер карты: ").strip()
    rec = find_card_record(number, data_path)
    if not rec:
        print("Карта с таким номером не найдена.")
        return None

    attempts = 0
    atm = ATM(Card(rec["first_name"], rec["last_name"], rec["pin"], rec["number"]), balance=rec.get("balance", 0), transactions=rec.get("transactions", []))
    while attempts < MAX_PIN_ATTEMPTS and not atm.is_authenticated:
        try:
            entered = getpass("Введите PIN: ")
        except Exception:
            entered = input("Введите PIN: ")
        if atm.authenticate(entered):
            print(f"PIN верный. Доступ разрешён. Добро пожаловать, {atm.card.first_name}!")
            return rec, atm
        attempts += 1
        print(f"Неверный PIN. Осталось попыток: {MAX_PIN_ATTEMPTS - attempts}")
    print("Превышено количество попыток. Доступ заблокирован.")
    return None


def print_menu() -> None:
    print("\n" + "=" * 40)
    print("Меню банкомата:")
    print("1. Просмотреть баланс")
    print("2. Пополнить счёт")
    print("3. Снять наличные")
    print("4. История транзакций")
    print("5. Сменить PIN")
    print("6. Показать данные карты")
    print("0. Выход")
    print("=" * 40)


def run_atm_simulation(data_path: str = DATA_FILE) -> None:
    """Главная функция — пользовательский цикл банкомата с реестром карт и сохранением в JSON."""
    print("Добро пожаловать в симулятор банкомата.")

    # Главный цикл: предложим выбор — регистрация или вход
    while True:
        print("\nДоступные действия:")
        print("1. Зарегистрировать новую карту")
        print("2. Войти по номеру карты")
        print("0. Выйти")
        choice = input("Выберите действие (0-2): ").strip()
        if choice == "1":
            rec = register_card_interactive(data_path)
            # после регистрации можно сразу войти или вернуться в меню
            continue
        elif choice == "2":
            auth = authenticate_card_interactive(data_path)
            if not auth:
                continue
            rec, atm = auth
            # Сохранение будет происходить после каждой операции (обновляем rec и сохраняем)
            while True:
                print_menu()
                opt = input("Выберите пункт меню (0-6): ").strip()
                if opt == "1":
                    print(atm.get_balance())
                elif opt == "2":
                    try:
                        amount = prompt_int("Введите сумму для пополнения (целое число): ")
                    except KeyboardInterrupt:
                        print("Отмена операции. Возврат в меню.")
                        continue
                    print(atm.deposit(amount))
                    # обновляем запись и сохраняем
                    rec["balance"] = atm.balance
                    rec["transactions"] = atm.get_transactions()
                    update_card_record(rec, data_path)
                elif opt == "3":
                    try:
                        amount = prompt_int("Введите сумму для снятия (целое число): ")
                    except KeyboardInterrupt:
                        print("Отмена операции. Возврат в меню.")
                        continue
                    print(atm.withdraw(amount))
                    rec["balance"] = atm.balance
                    rec["transactions"] = atm.get_transactions()
                    update_card_record(rec, data_path)
                elif opt == "4":
                    txs = atm.get_transactions()
                    if not txs:
                        print("Транзакций пока нет.")
                    else:
                        print("История транзакций:")
                        for i, (t_type, amt) in enumerate(txs, start=1):
                            print(f"{i}. {t_type}: {amt} {CURRENCY}")
                elif opt == "5":
                    try:
                        old = getpass("Введите текущий PIN: ")
                    except Exception:
                        old = input("Введите текущий PIN: ")
                    new = input("Введите новый PIN (4-6 цифр): ").strip()
                    msg = atm.change_pin(old, new)
                    print(msg)
                    # Сохраняем новый PIN и, при необходимости, баланс/транзакции
                    rec["pin"] = atm.card.pin
                    rec["balance"] = atm.balance
                    rec["transactions"] = atm.get_transactions()
                    update_card_record(rec, data_path)
                elif opt == "6":
                    print(f"Данные карты: Владелец: {atm.card.full_name()}, Номер карты: {atm.card.number}")
                elif opt == "0":
                    print("Выход из сессии пользователя.")
                    break
                else:
                    print("Некорректный выбор. Пожалуйста, введите номер пункта меню (0-6).")
        elif choice == "0":
            print("Спасибо за использование симулятора. До свидания!")
            break
        else:
            print("Некорректный выбор. Введите 0, 1 или 2.")

if __name__ == "__main__":
    try:
        run_atm_simulation()
    except KeyboardInterrupt:
        print("\nПрограмма прервана пользователем. Выход.")
        sys.exit(0)

# End of atm_simulator.py
