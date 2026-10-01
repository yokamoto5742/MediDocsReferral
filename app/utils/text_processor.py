import re

from app.core.constants import DEFAULT_SECTION_NAMES, SECTION_DETECTION_PATTERN

SECTION_ALIASES = {
    "その他": "備考",
    "補足": "備考",
    "メモ": "備考"
}

# 行頭がセクション名で始まれば見出しとみなすため、「備考として〜」のような本文の行にも一致する
_SECTION_HEADING = re.compile(
    SECTION_DETECTION_PATTERN.format(
        sections="|".join(
            re.escape(name) for name in [*DEFAULT_SECTION_NAMES, *SECTION_ALIASES]
        )
    )
)

# 全角文字(日本語・全角記号)。英数字間のスペースは薬剤名や検査値の可読性のため保持する
_FULLWIDTH_CHAR = r"[　-ヿ㐀-鿿豈-﫿＀-￯]"
_SPACE_ADJACENT_FULLWIDTH = re.compile(
    rf"(?<={_FULLWIDTH_CHAR}) +| +(?={_FULLWIDTH_CHAR})"
)
_TRAILING_SPACES = re.compile(r"[ \t]+$", re.MULTILINE)


def format_output_summary(summary_text: str) -> str:
    """AI出力のフォーマットを整形"""
    processed_text = (
        summary_text.replace('*', '')
        .replace('＊', '')
        .replace('#', '')
    )
    processed_text = _SPACE_ADJACENT_FULLWIDTH.sub('', processed_text)
    processed_text = _TRAILING_SPACES.sub('', processed_text)

    return processed_text


def _match_section(line: str) -> tuple[str, str] | None:
    """行がセクション見出しなら (セクション名, 同じ行に続く内容) を返す"""
    match = _SECTION_HEADING.match(line)
    if not match:
        return None
    name = match.group(1)
    return SECTION_ALIASES.get(name, name), match.group(2).strip()


def parse_output_summary(summary_text: str) -> dict[str, str]:
    """AI出力をセクションごとに分割してパース"""
    sections = {section: "" for section in DEFAULT_SECTION_NAMES}
    current_section = None

    for line in summary_text.split('\n'):
        line = line.strip()
        if not line:
            continue

        heading = _match_section(line)
        if heading:
            current_section, content = heading
            # 見出しと同じ行の内容は、そのセクションの既存の内容を置き換える
            if content:
                sections[current_section] = content
        elif current_section:
            if sections[current_section]:
                sections[current_section] += "\n" + line
            else:
                sections[current_section] = line

    return sections
