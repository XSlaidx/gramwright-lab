"""Доказательство, что блоки «Последнее решение» считаются, а не набраны руками.

Метод: подменяем каталог журналов на временный, кладём туда фиктивные записи, собираем тело страницы
и проверяем, что числа взялись ИЗ ЖУРНАЛА. Затем меняем журнал и собираем снова: если блок статичный,
второй текст совпадёт с первым, и тест упадёт.

Сети не требует: страница читает локальные файлы.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.normpath(os.path.join(HERE, "..", "gramwright-lab"))
sys.path.insert(0, LAB)

import contest_page as cp  # noqa: E402
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..")))
import site_build  # noqa: E402  (типографика правится на сборке каркаса, как на живой странице)


def write_journals(root: str, conf: int, model: str, p_up: float, side: str) -> None:
    with open(os.path.join(root, "ai-bee-journal.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "ts": "2026-10-18 09:05:00", "symbol": "ETHUSDT", "bar_ms": 1792317600000,
            "price": 2418.24, "model": model, "side": side, "confidence": conf,
            "reason": "проверка: журнал подменён тестом", "allowed": side != "FLAT",
        }, ensure_ascii=False) + "\n")
    with open(os.path.join(root, "ai-learner-journal.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "kind": "learned_decision", "ts": "2026-10-18 09:03:00", "symbol": "ETHUSDT",
            "bar_ms": 1792317600000,
            "side": side, "p_up": p_up, "allowed": False,
            "expected_move_pct": 1.459, "needed_move_pct": 0.45,
            "reasons": [f"вероятность {p_up:.3f} внутри коридора 0.40…0.60"],
        }, ensure_ascii=False) + "\n")


def main() -> int:
    real_demo = cp.DEMO
    with tempfile.TemporaryDirectory() as tmp:
        cp.DEMO = tmp
        try:
            write_journals(tmp, 77, "test:model-a", 0.9123, "LONG")
            first = site_build.normalize_numbers(cp.render_body())

            assert "уверенность 77 из 100" in first, "блок ИИ не взял уверенность из журнала"
            assert "test:model-a" in first, "блок ИИ не взял модель из журнала"
            assert "Вероятность роста 0,912" in first, "блок модели не взял p_up из журнала"
            assert "0,40…0,60" in first, "коридор не переведён в запятую"
            print("  ✓ первая сборка: числа взяты из журнала (77, 0,912, test:model-a)")

            write_journals(tmp, 41, "test:model-b", 0.6234, "SHORT")
            second = site_build.normalize_numbers(cp.render_body())

            assert "уверенность 41 из 100" in second, "вторая сборка не изменилась — блок статичный"
            assert "Вероятность роста 0,623" in second, "p_up не обновился"
            assert "test:model-b" in second, "модель не обновилась"
            assert "уверенность 77 из 100" not in second, "осталось старое значение"
            print("  ✓ вторая сборка: блоки обновились (41, 0,623, test:model-b)")

            # время решения и бар печатаются — иначе «последнее» не отличить от «когда-то»
            assert "решение 18.10" in second and "бар 18.10" in second, "нет времени решения/бара"
            print("  ✓ время решения и бар печатаются")
        finally:
            cp.DEMO = real_demo
    print("\nитог: блоки считаются при сборке")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
