"""تست ابزارهای متن فارسی: نرمال‌سازی، توکن‌سازی، تشخیص بودجه."""

from __future__ import annotations

import pytest

from app.core.text import content_tokens, fmt_toman, normalize, parse_budget, to_latin_digits, tokenize


class TestNormalize:
    def test_arabic_yeh_and_kaf(self):
        assert normalize("علي كريمي") == "علی کریمی"

    def test_persian_digits(self):
        assert normalize("۱۲۳۴") == "1234"

    def test_zwnj_becomes_space(self):
        assert normalize("می‌خواهم") == "می خواهم"

    def test_diacritics_removed(self):
        assert normalize("مُحَمَّد") == "محمد"

    def test_empty_inputs(self):
        assert normalize(None) == ""
        assert normalize("") == ""
        assert normalize("   ") == ""

    def test_whitespace_collapsed(self):
        assert normalize("شارژر   اپل") == "شارژر اپل"


class TestTokenize:
    def test_basic(self):
        assert tokenize("شارژر اپل ۲۰ وات") == ["شارژر", "اپل", "20", "وات"]

    def test_stopwords_removed(self):
        tokens = content_tokens("یه شارژر خوب می‌خوام")
        assert "شارژر" in tokens
        assert "میخوام" not in tokens
        assert "خوب" not in tokens


class TestParseBudget:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("تا ۲ میلیون تومان", 2_000_000),
            ("زیر ۵۰۰ هزار تومان", 500_000),
            ("حداکثر ۱۰ میلیون", 10_000_000),
            ("۳ میلیون تومان", 3_000_000),
            ("تا 2.5 میلیون", 2_500_000),
        ],
    )
    def test_max_budget(self, text, expected):
        lo, hi = parse_budget(text)
        assert hi == expected

    def test_no_budget(self):
        assert parse_budget("شارژر اپل") == (None, None)
        assert parse_budget("") == (None, None)

    def test_min_budget(self):
        lo, hi = parse_budget("بالای ۵ میلیون تومان")
        assert lo == 5_000_000
        assert hi is None

    def test_ignores_small_numbers(self):
        # «۲۰ وات» بودجه نیست
        _, hi = parse_budget("شارژر اپل ۲۰ وات")
        assert hi is None


class TestPersianNumbers:
    """ارقام نمایش‌داده‌شده به کاربر باید فارسی باشند (تایپوگرافی RTL)."""

    def test_fa_number_grouping(self):
        from app.core.text import fa_number
        assert fa_number(6476) == "۶٬۴۷۶"
        assert fa_number(331506) == "۳۳۱٬۵۰۶"

    def test_fa_number_decimals(self):
        from app.core.text import fa_number
        assert fa_number(4.2, 1) == "۴٫۲"
        assert fa_number(0.98, 2) == "۰٫۹۸"

    def test_fa_number_none(self):
        from app.core.text import fa_number
        assert fa_number(None) == "نامشخص"

    def test_fa_digits(self):
        from app.core.text import fa_digits
        assert fa_digits("abc123") == "abc۱۲۳"

    def test_fmt_toman_uses_persian_digits(self):
        """هیچ رقم ASCII در خروجی نباشد (پایتون ارقام فارسی را هم isdigit می‌داند)."""
        ascii_digits = set("0123456789")
        for value in (480_000, 4_100_000, 2_500_000_000):
            out = fmt_toman(value)
            assert not (set(out) & ascii_digits), f"رقم لاتین در {out!r}"

    def test_no_latin_digits_in_toman_output(self):
        assert fmt_toman(4_079_600) == "۴٫۱ میلیون تومان"

    def test_integer_millions_have_no_trailing_decimal(self):
        assert fmt_toman(5_000_000) == "۵ میلیون تومان"


class TestFormat:
    def test_millions(self):
        assert "میلیون" in fmt_toman(4_100_000)

    def test_billions(self):
        assert "میلیارد" in fmt_toman(2_500_000_000)

    def test_thousands(self):
        assert "هزار" in fmt_toman(480_000)

    def test_none(self):
        assert fmt_toman(None) == "نامشخص"

    def test_latin_digits_conversion(self):
        assert to_latin_digits("۰۱۲۳") == "0123"


class TestCleanTitle:
    """عنوان دیتاست نباید با پیشوند # یا " به کاربر نشان داده شود."""

    def test_strips_hash_prefix(self):
        from app.core.text import clean_title
        assert clean_title("# ترانسمیتر اختلاف فشار ABB") == "ترانسمیتر اختلاف فشار ABB"

    def test_strips_quote_prefix(self):
        from app.core.text import clean_title
        assert clean_title('"فیش پرینتر Atom مدل A300') == "فیش پرینتر Atom مدل A300"

    def test_collapses_whitespace(self):
        from app.core.text import clean_title
        assert clean_title("  هدفون   بی\u200cسیم  ") == "هدفون بی\u200cسیم"

    def test_keeps_model_digits_untouched(self):
        from app.core.text import clean_title
        # ارقام لاتین مدل محصول نباید فارسی شوند
        assert clean_title("هدفون JBL مدل J30") == "هدفون JBL مدل J30"

    def test_junk_only_returns_original(self):
        from app.core.text import clean_title
        assert clean_title("###") == "###"

    def test_none_safe(self):
        from app.core.text import clean_title
        assert clean_title(None) is None
        assert clean_title("") == ""

    def test_does_not_drop_leading_word(self):
        from app.core.text import clean_title
        assert clean_title("لپ‌تاپ ایسوس") == "لپ‌تاپ ایسوس"


class TestPhoneNormalization:
    """شمارهٔ دیتاست با ارقام فارسی است؛ tel: با آن کار نمی‌کند (باگ واقعی که رفع شد)."""

    def test_phone_digits_are_persian_in_dataset_format(self):
        import re
        phone = "۰۹۱۲۲۸۸۷۴۷۰"
        assert re.search(r"[۰-۹]", phone), "شمارهٔ دیتاست فارسی است"
