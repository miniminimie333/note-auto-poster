import anthropic
import asyncio
from playwright.async_api import async_playwright
import os
import random

TOPICS = [
    "唾液の力と疲労回復の意外な関係",
    "歯磨きのタイミングが体のリズムを整える理由",
    "口の中の炎症が疲れやすさに繋がるメカニズム",
    "舌の状態でわかる体の疲れサイン",
    "デンタルフロスが睡眠の質を高める科学的根拠",
    "口腔ケアで免疫力を上げる毎日の習慣",
    "食後の口ケアで午後の眠気を防ぐ方法",
    "歯周病と慢性疲労の深い繋がり",
    "朝の口臭が体の回復状態を教えてくれる",
    "マウスウォッシュと自律神経の意外な関係",
    "口腔マッサージで疲れを素早くリセットする",
    "虫歯予防が全身の炎症を抑える仕組み",
    "呼吸と口腔ケアで疲れにくい体を作る",
    "食いしばりが疲労を悪化させる理由と対策",
    "口の乾燥と慢性疲労のサイクルを断ち切る方法",
]


def generate_article() -> tuple[str, str]:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    hint = random.choice(TOPICS)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        messages=[{
            "role": "user",
            "content": f"""あなたは「口腔健康×疲労改善」の情報を発信するnoteクリエイターです。
本日のテーマヒント：「{hint}」

以下の厳密な形式で記事を書いてください。

TITLE: ここにタイトル（25文字以内、惹きつける表現で）

CONTENT:
ここに本文（1200〜1600文字。導入→【見出し】×3〜4セクション→まとめ の構成。
対象は30〜50代の健康意識が高い女性。体験談・具体的なアドバイスを含む親しみやすい文体。）
""",
        }],
    )

    raw = response.content[0].text
    title = ""
    content = ""

    if "TITLE:" in raw and "CONTENT:" in raw:
        after_title = raw.split("TITLE:")[1]
        title = after_title.split("\n")[0].strip()
        content = after_title.split("CONTENT:")[1].strip()

    if not title or not content:
        raise ValueError(f"記事の解析に失敗しました。\n出力:\n{raw[:500]}")

    return title, content


def fact_check_article(title: str, content: str) -> tuple[str, str]:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{
            "role": "user",
            "content": f"""以下のnote記事のファクトチェックをしてください。

タイトル：{title}

本文：
{content}

以下の観点で確認・修正してください：
1. 医学・健康に関する主張が科学的根拠に基づいているか
2. 効果を断言しすぎている表現がないか（「必ず〜」「絶対に〜」など）
3. 誤解を招く表現や誇張がないか
4. 口腔ケアと疲労改善に関して不正確な情報がないか

問題がある箇所は修正し、以下の形式で出力してください：

TITLE: （修正後のタイトル。問題なければ元のまま）

CONTENT:
（修正後の本文。問題なければ元のまま）

ISSUES:
（修正した点のリスト。問題なければ「なし」）
""",
        }],
    )

    raw = response.content[0].text
    title_out = title
    content_out = content
    issues = "なし"

    if "TITLE:" in raw and "CONTENT:" in raw:
        after_title = raw.split("TITLE:")[1]
        title_out = after_title.split("\n")[0].strip()
        content_out = after_title.split("CONTENT:")[1].split("ISSUES:")[0].strip()

    if "ISSUES:" in raw:
        issues = raw.split("ISSUES:")[1].strip()

    print(f"  ファクトチェック結果: {issues}")
    return title_out, content_out


async def post_to_note(title: str, content: str) -> None:
    email = os.environ["NOTE_EMAIL"]
    password = os.environ["NOTE_PASSWORD"]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx.new_page()

        try:
            # --- ログイン ---
            print("  ログイン中...")
            await page.goto("https://note.com/login", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(1000)

            await page.fill('input[type="email"]', email)
            await page.fill('input[type="password"]', password)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle", timeout=20000)

            if "login" in page.url:
                await page.screenshot(path="login_error.png")
                raise RuntimeError("ログインに失敗しました。メール・パスワードを確認してください。")

            print("  ログイン成功")

            # --- 新規記事作成ページへ ---
            await page.goto("https://note.com/new/text", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            # --- タイトル入力 ---
            title_selector = (
                'textarea[placeholder*="タイトル"], '
                'input[placeholder*="タイトル"], '
                '[data-placeholder*="タイトル"]'
            )
            await page.wait_for_selector(title_selector, timeout=15000)
            title_el = page.locator(title_selector).first
            await title_el.click()
            await title_el.fill(title)
            await page.wait_for_timeout(500)

            # --- 本文入力（ProseMirrorエディタ） ---
            body_selector = '.ProseMirror, [contenteditable="true"]'
            await page.wait_for_selector(body_selector, timeout=15000)
            body_el = page.locator(body_selector).first
            await body_el.click()
            await page.wait_for_timeout(500)

            # JavaScriptで一括挿入（キーイベントより速く確実）
            await page.evaluate(
                "(text) => { document.execCommand('insertText', false, text); }",
                content,
            )
            await page.wait_for_timeout(1000)

            # --- 公開設定ボタン ---
            publish_btn_selector = 'button:has-text("公開設定"), button:has-text("投稿する")'
            await page.wait_for_selector(publish_btn_selector, timeout=10000)
            await page.click(publish_btn_selector)
            await page.wait_for_timeout(2000)

            # --- モーダル内の投稿ボタン ---
            modal_btn_selector = (
                'button:has-text("投稿"), '
                'button:has-text("公開する"), '
                'button:has-text("今すぐ公開")'
            )
            modal_btn = page.locator(modal_btn_selector).first
            if await modal_btn.is_visible():
                await modal_btn.click()
                await page.wait_for_load_state("networkidle", timeout=20000)

            print(f"  投稿完了: {page.url}")

        except Exception as exc:
            await page.screenshot(path="error.png")
            raise exc
        finally:
            await browser.close()


async def main() -> None:
    print("📝 記事を生成中...")
    title, content = generate_article()
    print(f"  タイトル: {title}")

    print("🔍 ファクトチェック中...")
    title, content = fact_check_article(title, content)
    print(f"  確認済みタイトル: {title}")

    print("🚀 noteに投稿中...")
    await post_to_note(title, content)

    print("✅ 完了！")


if __name__ == "__main__":
    asyncio.run(main())
