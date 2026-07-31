import smtplib
import html as html_module
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
from datetime import datetime
import requests
import markdown2
import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode
from bs4 import BeautifulSoup

from .config import OutputSettings, GlobalConfig, get_secret
from .rss_fetcher import Article
from .article_utils import extract_domain, extract_topic_keywords


class DocumentGenerator:
    def __init__(self, output_settings: OutputSettings, global_config: GlobalConfig):
        self.output_settings = output_settings
        self.global_config = global_config
        self.digest_history_file = "history/digest_history.json"

    def feedback_instructions_markdown(self) -> str:
        return (
            "## Feedback Shortcuts\n\n"
            "如果你更喜欢邮件回复，建议统一用下面这个开头话术，这样系统更容易自动识别，而且更省 token：\n\n"
            "```text\n"
            "主题建议：Re: MorningModel Feedback\n\n"
            "晨报反馈：栏目=AI Top 10；来源 techcrunch.com 降权，理由：重复多 | 主题 agents 优先，理由：值得长期跟踪\n"
            "```\n\n"
            "如果你想手动录入，也可以直接运行这些命令：\n\n"
            "```bash\n"
            "python scripts/record_feedback.py --collection \"AI Top 10\" --kind source --target techcrunch.com --action deprioritize --reason \"重复多\"\n"
            "python scripts/record_feedback.py --collection \"AI Top 10\" --kind source --target openai.com --action trust --reason \"一手来源\"\n"
            "python scripts/record_feedback.py --collection \"AI Top 10\" --kind topic --target agents --action prefer --reason \"值得长期跟踪\"\n"
            "python scripts/record_feedback.py --collection \"Finance Top 10\" --kind topic --target ecb --action deprioritize --reason \"同题过密\"\n"
            "```\n\n"
            "Action options:\n"
            "- Source: `trust`, `watch`, `deprioritize`, `block`\n"
            "- Topic: `prefer`, `watch`, `deprioritize`, `block`\n"
        )
        
    def _ensure_history_dir(self):
        """Ensure the history directory exists."""
        Path("history").mkdir(exist_ok=True)
        
    def load_previous_digests(self) -> List[Dict]:
        """Load the last n digests from history."""
        self._ensure_history_dir()
        if not os.path.exists(self.digest_history_file):
            return []
            
        try:
            with open(self.digest_history_file, 'r', encoding='utf-8') as f:
                all_digests = json.load(f)
            # Return the most recent digests up to context_digest_size
            return all_digests[-self.global_config.context_digest_size:]
        except Exception as e:
            print(f"Warning: Could not load digest history: {e}")
            return []
    
    def save_digest_to_history(self, collection_summaries: Dict[str, str], date: datetime):
        """Save only the collection summaries to history, without feed reports and detailed article summaries."""
        self._ensure_history_dir()
        
        # Load existing digests
        all_digests = []
        if os.path.exists(self.digest_history_file):
            try:
                with open(self.digest_history_file, 'r', encoding='utf-8') as f:
                    all_digests = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load existing digest history: {e}")
        
        # Build a clean digest with only the collection summaries
        clean_digest_parts = [f"# Daily Digest - {date.strftime('%Y-%m-%d')}", "## General Overview"]
        for collection_name, summary in collection_summaries.items():
            clean_digest_parts.append(f"\n### {collection_name}\n")
            clean_digest_parts.append(summary)
        
        clean_digest_content = "\n".join(clean_digest_parts)
        
        # Add the new digest
        new_digest = {
            "date": date.strftime('%Y-%m-%d'),
            "content": clean_digest_content
        }
        all_digests.append(new_digest)
        
        # Keep only the most recent digests (double the context size to have some buffer)
        max_stored = max(self.global_config.context_digest_size * 2, 10)
        all_digests = all_digests[-max_stored:]
        
        # Save back to file
        try:
            with open(self.digest_history_file, 'w', encoding='utf-8') as f:
                json.dump(all_digests, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save digest to history: {e}")
            
    def get_context_for_llm(self) -> str:
        """Get formatted context from previous digests for LLM consumption."""
        previous_digests = self.load_previous_digests()
        if not previous_digests:
            return ""
            
        context_parts = ["Here are the previous digests for context (avoid repeating similar news):"]
        for digest in previous_digests:
            context_parts.append(f"\n--- Digest from {digest['date']} ---")
            context_parts.append(digest['content'])
            
        context_parts.append("\n--- End of previous digests ---\n")
        return "\n".join(context_parts)

    def _parse_recipient_emails(self, recipient_email: str) -> List[str]:
        """Parse one or more recipient emails from comma/semicolon/newline-separated text."""
        return [
            email.strip()
            for email in re.split(r"[,;\n]+", recipient_email or "")
            if email.strip()
        ]

    def _section_title(self, collection_name: str) -> str:
        normalized = collection_name.lower()
        if "research" in normalized or "safety" in normalized:
            return "AI Research & Safety Top 10"
        if "ai" in normalized:
            return "AI Top 10"
        if "finance" in normalized:
            return "Finance Top 10"
        return collection_name

    def _generate_one_line_take(self, collection_summaries: Dict[str, str]) -> str:
        """Static fallback used when the LLM one-line take is unavailable."""
        lang = (self.global_config.llm_settings.output_language or "English").lower()
        is_chinese = "chinese" in lang or "中文" in lang

        available_sections = [
            self._section_title(name)
            for name, summary in collection_summaries.items()
            if summary
            and not summary.startswith("[ERROR:")
            and not summary.startswith("[Error:")
            and summary not in {
                "No new articles found.",
                "No articles selected for fetching.",
                "No articles with extractable content.",
                "No articles with valid summaries.",
                "No content available for collection summary.",
            }
        ]
        if not available_sections:
            return (
                "今天没有足够高质量的新内容形成明确主线，建议等待下一次更新。"
                if is_chinese
                else "Not enough high-quality content today to identify a clear main thread."
            )

        has_ai  = "AI Top 10" in available_sections
        has_fin = "Finance Top 10" in available_sections

        if is_chinese:
            if has_ai and has_fin:
                return "今天重点同时看 AI 产业主线与全球宏观/市场风险偏好变化，继续跟踪大模型基础设施、央行预期和风险资产定价。"
            if has_ai:
                return "今天重点看 AI 产业与政策主线，继续跟踪 frontier models、agents 和算力基础设施变化。"
            if has_fin:
                return "今天重点看全球宏观与市场风险偏好变化，继续跟踪央行预期、利率路径和主要资产定价。"
            return "今天重点看各栏目中最具国际影响力的新变化，并继续跟踪其后续扩散。"
        else:
            if has_ai and has_fin:
                return "Today focus on AI industry trends and global macro/risk-appetite shifts; track model infrastructure, central bank signals, and risk-asset pricing."
            if has_ai:
                return "Today focus on the AI industry and policy front; track frontier models, agents, and compute infrastructure changes."
            if has_fin:
                return "Today focus on global macro and risk-appetite shifts; track central bank expectations, rate paths, and major asset pricing."
            return "Today focus on the most internationally significant new developments across all sections and follow their downstream impact."

    def _feedback_recipient(self) -> str:
        return (
            os.getenv("BETTER_MORNING_FEEDBACK_EMAIL")
            or os.getenv("BETTER_MORNING_FEEDBACK_IMAP_USERNAME")
            or ""
        ).strip()

    def _feedback_mailto(self, body: str) -> str:
        recipient = self._feedback_recipient()
        query = urlencode(
            {
                "subject": "Re: MorningModel Feedback",
                "body": body,
            }
        )
        return f"mailto:{recipient}?{query}"

    def _article_feedback_actions_html(
        self,
        collection_name: str,
        article: Article,
    ) -> str:
        source = extract_domain(str(article.source_url or article.link))
        topics = extract_topic_keywords(article.title, article.summary, limit=2)
        topic = topics[0] if topics else ""
        title = html_module.escape(article.title)
        source_label = html_module.escape(source or "source")

        reason_title = article.title[:90]
        if topic:
            more_body = (
                f"晨报反馈：栏目={collection_name}；主题 {topic} 优先，"
                f"理由：多看类似：{reason_title}"
            )
            less_body = (
                f"晨报反馈：栏目={collection_name}；主题 {topic} 减少，"
                f"理由：少看类似：{reason_title}"
            )
        else:
            more_body = (
                f"晨报反馈：栏目={collection_name}；来源 {source} 观察，"
                f"理由：多看类似但未抽到主题：{reason_title}"
            )
            less_body = (
                f"晨报反馈：栏目={collection_name}；来源 {source} 降权，"
                f"理由：少看类似但未抽到主题：{reason_title}"
            )
        source_body = (
            f"晨报反馈：栏目={collection_name}；来源 {source} 降权，"
            f"理由：少看这个来源：{reason_title}"
        )

        more_href = html_module.escape(self._feedback_mailto(more_body), quote=True)
        less_href = html_module.escape(self._feedback_mailto(less_body), quote=True)
        source_href = html_module.escape(self._feedback_mailto(source_body), quote=True)

        return f"""
        <details class="article-feedback">
          <summary title="调整下次推荐"></summary>
          <span class="article-feedback-menu">
            <span class="article-feedback-source">{source_label}</span>
            <a href="{more_href}">多一点</a>
            <a href="{less_href}">少一点</a>
            <a href="{source_href}">少来源</a>
          </span>
        </details>"""

    def _summary_with_feedback_actions_html(
        self,
        content_html: str,
        collection_name: str,
        articles: List[Article],
    ) -> str:
        valid_articles = [
            article
            for article in articles
            if article.title and article.summary and not article.summary.startswith("[Error:")
        ]
        if not valid_articles:
            return content_html

        soup = BeautifulSoup(content_html, "html.parser")
        list_items = soup.find_all("li")
        for list_item, article in zip(list_items, valid_articles):
            title_node = list_item.find("strong")
            if title_node is None:
                continue
            feedback_fragment = BeautifulSoup(
                self._article_feedback_actions_html(collection_name, article),
                "html.parser",
            )
            title_node.insert_after(feedback_fragment)
        return str(soup)

    def generate_email_html(
        self,
        collection_summaries: Dict[str, str],
        date: datetime,
        fetch_reports: Optional[Dict[str, dict]] = None,
        collection_errors: Optional[Dict[str, str]] = None,
        one_line_take: Optional[str] = None,
        articles_by_collection: Optional[Dict[str, List[Article]]] = None,
    ) -> str:
        """Generates a newspaper-style HTML email with only summaries; feed report is collapsed."""
        _EMPTY_SUMMARIES = {
            "No new articles found.",
            "No articles selected for fetching.",
            "No articles with extractable content.",
            "No articles with valid summaries.",
            "No content available for collection summary.",
        }

        date_str = date.strftime("%A, %B %-d, %Y")
        one_line = html_module.escape(
            one_line_take or self._generate_one_line_take(collection_summaries)
        )

        sections_html = ""
        for collection_name, summary in collection_summaries.items():
            if (
                not summary
                or summary in _EMPTY_SUMMARIES
                or summary.startswith("[ERROR:")
                or summary.startswith("[Error:")
            ):
                continue
            section_title = html_module.escape(self._section_title(collection_name))
            content_html = markdown2.markdown(
                summary, extras=["fenced-code-blocks", "tables"]
            )
            content_html = self._summary_with_feedback_actions_html(
                content_html,
                collection_name,
                (articles_by_collection or {}).get(collection_name, []),
            )
            sections_html += f"""
    <div class="section">
      <div class="section-title">{section_title}</div>
      <div class="section-content">{content_html}</div>
    </div>"""

        # Build feed diagnostics table
        diag_rows = ""
        if fetch_reports:
            for report in fetch_reports.values():
                for feed in report.get("successful", []):
                    name = html_module.escape(feed.get("name", ""))
                    count = feed.get("articles_fetched", 0)
                    diag_rows += f'<tr><td class="ok">✓</td><td>{name}</td><td>{count} 篇</td></tr>'
                for feed in report.get("failed", []):
                    name = html_module.escape(feed.get("name", ""))
                    err = html_module.escape(str(feed.get("error", "")))[:80]
                    diag_rows += f'<tr><td class="fail">✗</td><td>{name}</td><td class="fail">{err}</td></tr>'

        diag_html = f"<table>{diag_rows}</table>" if diag_rows else "无抓取数据"

        errors_html = ""
        if collection_errors:
            items = "".join(
                f"<li><b>{html_module.escape(k)}</b>: {html_module.escape(v)}</li>"
                for k, v in collection_errors.items()
            )
            errors_html = f"""
    <details>
      <summary>栏目处理错误</summary>
      <div class="diag"><ul>{items}</ul></div>
    </details>"""

        return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI + Finance 国际晨报</title>
<style>
  body{{margin:0;padding:0;background:#f0ede8;font-family:Georgia,'Times New Roman',serif;color:#1a1a1a;}}
  .wrap{{max-width:680px;margin:24px auto;background:#fff;border:1px solid #c8c4bc;box-shadow:0 2px 8px rgba(0,0,0,.08);}}
  .masthead{{text-align:center;padding:28px 32px 18px;border-bottom:3px double #1a1a1a;}}
  .masthead h1{{margin:0 0 8px;font-size:28px;letter-spacing:.1em;text-transform:uppercase;font-weight:bold;}}
  .masthead .rule{{display:block;border:none;border-top:1px solid #1a1a1a;margin:6px auto;width:60%;}}
  .masthead .dateline{{font:11px/1 'Helvetica Neue',Arial,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:#888;}}
  .lede{{padding:18px 32px;border-bottom:1px solid #ddd;background:#faf8f4;}}
  .lede-label{{font:10px/1 'Helvetica Neue',Arial,sans-serif;letter-spacing:.18em;text-transform:uppercase;color:#aaa;margin-bottom:8px;}}
  .lede-text{{font-size:17px;line-height:1.6;font-style:italic;color:#222;}}
  .section{{padding:22px 32px;border-bottom:1px solid #ddd;}}
  .section-title{{font:10px/1 'Helvetica Neue',Arial,sans-serif;letter-spacing:.18em;text-transform:uppercase;color:#777;padding-bottom:8px;margin-bottom:18px;border-bottom:2px solid #1a1a1a;}}
  .section-content{{font-size:14px;line-height:1.8;}}
  .section-content a{{color:#1a1a1a;text-decoration:underline;}}
  .section-content ol{{padding-left:22px;margin:0;}}
  .section-content li{{margin-bottom:14px;}}
  .section-content p{{margin:0 0 10px;}}
  .section-content strong{{font-weight:bold;}}
  .article-feedback{{display:inline-block;position:relative;margin-left:4px;vertical-align:baseline;font-family:'Helvetica Neue',Arial,sans-serif;}}
  .article-feedback summary{{display:inline-block;width:12px;height:12px;padding:0;border:0;background:transparent;color:#aaa;font-size:0;line-height:1;cursor:pointer;list-style:none;vertical-align:baseline;}}
  .article-feedback summary::-webkit-details-marker{{display:none;}}
  .article-feedback summary::marker{{content:"";}}
  .article-feedback summary::before{{content:"▾";font-size:10px;line-height:12px;}}
  .article-feedback[open] summary{{color:#555;}}
  .article-feedback-menu{{display:none;position:absolute;z-index:5;top:16px;left:0;min-width:176px;padding:8px 9px;border:1px solid rgba(201,190,174,.58);border-radius:8px;background:rgba(250,248,244,.68);box-shadow:0 8px 28px rgba(0,0,0,.10);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);}}
  .article-feedback[open] .article-feedback-menu{{display:block;}}
  .article-feedback-source{{display:block;margin-bottom:5px;color:#aaa;font-size:10px;line-height:1.2;}}
  .article-feedback-menu a{{display:inline-block;margin:0 8px 3px 0;padding:2px 0;text-decoration:none;color:#555;background:transparent;font:11px/1.2 'Helvetica Neue',Arial,sans-serif;}}
  .article-feedback-menu a:hover{{text-decoration:underline;}}
  .footer-area{{padding:0 32px;}}
  details summary{{font:11px/1 'Helvetica Neue',Arial,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:#bbb;cursor:pointer;padding:14px 0;border-top:1px solid #eee;list-style:none;}}
  details summary::-webkit-details-marker{{display:none;}}
  details summary::before{{content:"▸ ";}}
  details[open] summary::before{{content:"▾ ";}}
  .feedback-howto pre{{white-space:pre-wrap;word-break:break-word;background:#faf8f4;border:1px solid #eee;padding:8px 10px;font:12px/1.6 'Courier New',monospace;}}
  .diag{{font:12px/1.65 'Helvetica Neue',Arial,sans-serif;color:#888;padding:6px 0 16px;}}
  .diag table{{width:100%;border-collapse:collapse;}}
  .diag td{{padding:3px 12px 3px 0;vertical-align:top;}}
  .diag ul{{margin:4px 0;padding-left:18px;}}
  .ok{{color:#2a8a4a;}}
  .fail{{color:#c33;}}
  .footer{{padding:18px 32px;text-align:center;font:11px/1.5 'Helvetica Neue',Arial,sans-serif;color:#ccc;background:#faf8f4;border-top:1px solid #ddd;}}
</style>
</head>
<body>
<div class="wrap">
  <div class="masthead">
    <h1>AI + Finance 国际晨报</h1>
    <hr class="rule">
    <div class="dateline">{date_str}</div>
  </div>
  <div class="lede">
    <div class="lede-label">今日主线</div>
    <div class="lede-text">{one_line}</div>
  </div>
  {sections_html}
  <div class="footer-area">
    <details>
      <summary>Feed 抓取报告</summary>
      <div class="diag">{diag_html}</div>
    </details>
    <details>
      <summary>人工反馈方式</summary>
      <div class="diag feedback-howto">
        <p>建议邮件主题以 <code>Re: MorningModel Feedback</code> 开头。</p>
        <p>推荐邮件回复统一以 <code>晨报反馈：</code> 开头，例如：</p>
        <pre>晨报反馈：栏目=AI Top 10；来源 techcrunch.com 降权，理由：重复多 | 主题 agents 优先，理由：值得长期跟踪</pre>
        <p>如果你想手动录入，也可以运行命令：</p>
        <pre>python scripts/record_feedback.py --collection "AI Top 10" --kind source --target techcrunch.com --action deprioritize --reason "重复多"</pre>
        <pre>python scripts/record_feedback.py --collection "AI Top 10" --kind topic --target agents --action prefer --reason "值得长期跟踪"</pre>
      </div>
    </details>
    {errors_html}
  </div>
  <div class="footer">Better Morning &nbsp;·&nbsp; 每日 07:00 北京时间送达</div>
</div>
</body>
</html>"""

    def generate_markdown_digest(
        self,
        collection_summaries: Dict[str, str],
        articles_by_collection: Dict[str, List[Article]],
        skipped_sources: List[str],
        date: datetime,
        fetch_reports: Optional[Dict[str, dict]] = None,
        collection_errors: Optional[Dict[str, str]] = None,
        one_line_take: Optional[str] = None,
        search_memory_reports: Optional[Dict[str, str]] = None,
    ) -> str:
        """Formats the digest with collection sections and a one-line take."""
        title = f"# AI + Finance Daily Brief - {date.strftime('%Y-%m-%d')}"

        overview_parts = []
        for collection_name, summary in collection_summaries.items():
            overview_parts.append(f"## {self._section_title(collection_name)}\n")
            overview_parts.append(summary)
        overview_parts.append("## One-line Take\n")
        overview_parts.append(
            one_line_take or self._generate_one_line_take(collection_summaries)
        )
        overview_section = "\n\n".join(overview_parts)

        # Generate collection errors section (for collections that failed early)
        collection_errors_section = ""
        if collection_errors:
            collection_errors_section = "\n## ⚠️ Collection Processing Errors\n\n"
            collection_errors_section += "*The following collections encountered errors and could not be fully processed. Please check your configuration:*\n\n"
            for collection_name, error_msg in collection_errors.items():
                collection_errors_section += f"- **{collection_name}**: {error_msg}\n"

        # Generate feed report section
        feed_report_section = ""
        if fetch_reports:
            all_successful = []
            all_failed = []
            total_articles = 0
            total_feeds = 0

            for collection_name, report in fetch_reports.items():
                # Defensive checks: handle missing or empty keys gracefully
                successful_feeds = report.get("successful", [])
                failed_feeds = report.get("failed", [])
                
                all_successful.extend(
                    [(s, collection_name) for s in successful_feeds]
                )
                all_failed.extend([(f, collection_name) for f in failed_feeds])
                total_articles += sum(
                    s.get("articles_fetched", 0) for s in successful_feeds
                )
                total_feeds += report.get("total_feeds", 0)

            success_rate = (
                len(all_successful) / total_feeds if total_feeds > 0 else 0
            )

            feed_report_section = f"\n## Feed Processing Report\n\n"
            feed_report_section += f"**Summary**: {len(all_successful)}/{total_feeds} feeds successful ({success_rate:.1%}) • {total_articles} articles fetched\n\n"

            if all_successful:
                feed_report_section += "### ✅ Successful Feeds\n\n"
                for feed, collection in all_successful:
                    feed_report_section += f"- **{feed['name']}** ({collection}): {feed['articles_fetched']} articles\n  `{feed['url']}`\n\n"

            if all_failed:
                feed_report_section += "### ❌ Failed Feeds\n\n"
                feed_report_section += (
                    "*Consider removing these feeds from your collections:*\n\n"
                )
                for feed, collection in all_failed:
                    feed_report_section += f"- **{feed['name']}** ({collection}): {feed['error']}\n  `{feed['url']}`\n\n"

        skipped_sources_section = ""
        if skipped_sources:
            skipped_sources_section = "\n## Skipped Sources\n\nThe following sources were skipped due to a high number of consecutive content extraction errors:\n\n"
            for source in skipped_sources:
                skipped_sources_section += f"- {source}\n"

        search_memory_section = ""
        if search_memory_reports:
            search_memory_section = "\n## Adaptive Search Debug Report\n\n"
            search_memory_section += (
                "*This section is for local debugging only. It shows how source memory, topic memory, diversity constraints, and exploration lanes shaped the current run.*\n\n"
            )
            for collection_name, report in search_memory_reports.items():
                if not report:
                    continue
                search_memory_section += f"### {collection_name}\n\n{report}\n\n"

        detailed_sections = ["## Detailed Summaries"]
        for collection_name, articles in articles_by_collection.items():
            # Filter out articles that might have failed summarization
            valid_articles = [
                a
                for a in articles
                if a.summary and not a.summary.startswith("[Error:")
            ]
            if not valid_articles:
                continue

            detailed_sections.append(f"\n### Collection: {collection_name}\n")
            for article in valid_articles:
                detailed_sections.append(f"#### {article.title}\n")
                detailed_sections.append(f"{article.summary}\n")

        # Assemble the final document
        final_document_parts = [title, overview_section]
        if collection_errors_section:
            final_document_parts.extend(["---", collection_errors_section])
        if feed_report_section:
            final_document_parts.extend(["---", feed_report_section])
        if skipped_sources_section:
            final_document_parts.extend(["---", skipped_sources_section])
        if search_memory_section:
            final_document_parts.extend(["---", search_memory_section])
        final_document_parts.extend(["---", self.feedback_instructions_markdown()])
        final_document_parts.extend(["---"] + detailed_sections)

        return "\n\n".join(final_document_parts)

    def send_via_email(
        self, subject: str, body: str, recipient_email: str, raw_html: bool = False
    ) -> bool:
        if (
            not self.output_settings.smtp_server
            or not self.output_settings.smtp_port
            or not self.output_settings.smtp_username_env
            or not self.output_settings.smtp_password_env
        ):
            print("Error: SMTP settings are incomplete. Cannot send email.")
            return False

        try:
            smtp_username = get_secret(
                self.output_settings.smtp_username_env, "SMTP Username"
            )
            smtp_password = get_secret(
                self.output_settings.smtp_password_env, "SMTP Password"
            )

            html_body = body if raw_html else markdown2.markdown(body)
            recipient_emails = self._parse_recipient_emails(recipient_email)
            if not recipient_emails:
                print("Error: No recipient email configured. Cannot send email.")
                return False

            # Create message with HTML content
            msg = MIMEMultipart()
            msg["From"] = smtp_username
            msg["To"] = ", ".join(recipient_emails)
            msg["Subject"] = subject

            # Attach only the HTML part
            msg.attach(MIMEText(html_body, "html"))

            if self.output_settings.smtp_port == 465:
                with smtplib.SMTP_SSL(
                    self.output_settings.smtp_server,
                    self.output_settings.smtp_port,
                    timeout=30,
                ) as server:
                    server.ehlo()
                    server.login(smtp_username, smtp_password)
                    server.send_message(msg, to_addrs=recipient_emails)
            else:
                with smtplib.SMTP(
                    self.output_settings.smtp_server,
                    self.output_settings.smtp_port,
                    timeout=30,
                ) as server:
                    server.ehlo()          # announce ourselves before STARTTLS
                    server.starttls()
                    server.ehlo()          # re-announce after TLS upgrade (required by RFC)
                    server.login(smtp_username, smtp_password)
                    server.send_message(msg, to_addrs=recipient_emails)
            print(
                "Email digest sent successfully to "
                + ", ".join(recipient_emails)
            )
            return True
        except Exception as e:
            import traceback
            print(f"Error sending email digest: {type(e).__name__}: {e}")
            traceback.print_exc()
            return False

    def create_github_release(
        self, tag_name: str, release_name: str, body: str, repo_slug: str
    ):
        if not self.output_settings.github_token_env:
            print(
                "Error: GitHub token environment variable not configured. Cannot create GitHub release."
            )
            return

        try:
            github_token = get_secret(
                self.output_settings.github_token_env, "GitHub Token"
            )
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
            }
            data = {
                "tag_name": tag_name,
                "name": release_name,
                "body": body,
                "draft": False,
                "prerelease": False,
            }

            # repo_slug should be in format 'owner/repo'
            api_url = f"https://api.github.com/repos/{repo_slug}/releases"

            response = requests.post(api_url, headers=headers, json=data)
            response.raise_for_status()  # Raise an exception for HTTP errors
            print(
                f"GitHub release '{release_name}' created successfully at {response.json()['html_url']}"
            )
        except requests.exceptions.RequestException as e:
            print(f"Error creating GitHub release: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while creating GitHub release: {e}")
