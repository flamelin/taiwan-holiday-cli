#!/usr/bin/env python3
"""查詢台灣政府行政機關放假日（資料來源：data/{西元年}.json，由 update.py 產生）。"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
LONG_WEEKEND_MIN_DAYS = 3


@dataclass(frozen=True)
class Day:
    date: date
    week: str
    is_off: bool
    note: str

    @property
    def is_national_holiday(self) -> bool:
        """放假且有備註（含補假）；一般週末沒有備註。"""
        return self.is_off and bool(self.note)

    def label(self) -> str:
        return f"{self.date.isoformat()}（{self.week}）"


def load_days() -> list[Day]:
    days = []
    for path in sorted(DATA_DIR.glob("*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")):
            days.append(
                Day(
                    date=datetime.strptime(row["西元日期"], "%Y%m%d").date(),
                    week=row["星期"],
                    is_off=row["是否放假"] == "2",
                    note=row["備註"].strip(),
                )
            )
    days.sort(key=lambda d: d.date)
    return days


def parse_date(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"無法解析日期：{value}（格式：YYYY-MM-DD、YYYY/MM/DD 或 YYYYMMDD）")


def days_between(base: date, target: date) -> str:
    diff = (target - base).days
    if diff == 0:
        return "今天"
    return f"{diff} 天後" if diff > 0 else f"{-diff} 天前"


def long_weekends(days: list[Day]) -> list[list[Day]]:
    """連續放假且天數 >= LONG_WEEKEND_MIN_DAYS 的區段。"""
    runs, current = [], []
    for day in days:
        if day.is_off and current and (day.date - current[-1].date).days == 1:
            current.append(day)
            continue
        if len(current) >= LONG_WEEKEND_MIN_DAYS:
            runs.append(current)
        current = [day] if day.is_off else []
    if len(current) >= LONG_WEEKEND_MIN_DAYS:
        runs.append(current)
    return runs


def data_range(days: list[Day]) -> str:
    return f"{days[0].date.isoformat()} ~ {days[-1].date.isoformat()}"


def cmd_check(days: list[Day], base: date, verbose: bool) -> int:
    day = next((d for d in days if d.date == base), None)
    if day is None:
        print(f"查無 {base.isoformat()} 的資料（資料範圍：{data_range(days)}）", file=sys.stderr)
        return 1
    if not verbose:
        print("Y" if day.is_off else "N")
        return 0
    status = "放假" if day.is_off else "上班"
    print(f"{day.label()} {status}" + (f"：{day.note}" if day.note else ""))
    return 0


def cmd_next(days: list[Day], base: date) -> int:
    day = next((d for d in days if d.date > base and d.is_national_holiday), None)
    if day is None:
        print(f"資料中查無 {base.isoformat()} 之後的國定假日（資料範圍：{data_range(days)}）", file=sys.stderr)
        return 1
    print(f"{day.label()} {day.note}（{days_between(base, day.date)}）")
    return 0


def cmd_prev(days: list[Day], base: date) -> int:
    day = next((d for d in reversed(days) if d.date < base and d.is_national_holiday), None)
    if day is None:
        print(f"資料中查無 {base.isoformat()} 之前的國定假日（資料範圍：{data_range(days)}）", file=sys.stderr)
        return 1
    print(f"{day.label()} {day.note}（{days_between(base, day.date)}）")
    return 0


def cmd_long(days: list[Day], base: date) -> int:
    run = next((r for r in long_weekends(days) if r[0].date > base), None)
    if run is None:
        print(f"資料中查無 {base.isoformat()} 之後的連假（資料範圍：{data_range(days)}）", file=sys.stderr)
        return 1
    print(f"{run[0].label()} ~ {run[-1].label()}，共 {len(run)} 天（{days_between(base, run[0].date)}）")
    for day in run:
        print(f"  {day.label()}" + (f" {day.note}" if day.note else ""))
    return 0


COMMANDS = {
    "check": ("查詢某天是否放假（預設今天），放假輸出 Y、上班輸出 N", cmd_check),
    "next": ("下一個國定假日", cmd_next),
    "prev": ("上一個國定假日", cmd_prev),
    "long": (f"下一個連假（連續放假 {LONG_WEEKEND_MIN_DAYS} 天以上）", cmd_long),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="台灣政府行政機關放假日查詢")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, (help_text, _) in COMMANDS.items():
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.add_argument("date", nargs="?", type=parse_date, default=date.today(), help="基準日期，預設今天")
        if name == "check":
            p.add_argument("-v", "--verbose", action="store_true", help="顯示日期、星期與備註")
    args = parser.parse_args()

    days = load_days()
    if not days:
        print("data/ 中沒有資料，請先執行 python3 update.py", file=sys.stderr)
        return 1
    handler = COMMANDS[args.command][1]
    if args.command == "check":
        return handler(days, args.date, args.verbose)
    return handler(days, args.date)


if __name__ == "__main__":
    sys.exit(main())
