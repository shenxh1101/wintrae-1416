from typing import List, Dict, Optional
from collections import defaultdict
from datetime import datetime
import os

import pandas as pd

from models import Conversation, ReviewResult, QualityReport, Agent, RuleType


class ReportService:
    SCORE_THRESHOLD_PASS = 80.0
    SCORE_THRESHOLD_ATTENTION = 70.0
    MIN_SAMPLES_FOR_TRAINING = 2
    PASS_RATE_FOR_TRAINING = 0.6

    def generate_report(
        self,
        sampled_conversations: List[Conversation],
        reviews: Dict[str, ReviewResult],
        agents: List[Agent],
        report_date: Optional[str] = None
    ) -> QualityReport:
        if report_date is None:
            report_date = datetime.now().strftime("%Y-%m-%d")

        report = QualityReport(report_date=report_date)
        report.total_sampled = len(sampled_conversations)

        reviewed_convs = []
        review_list = []
        conv_map = {c.conv_id: c for c in sampled_conversations}

        for conv_id, review in reviews.items():
            if conv_id in conv_map and review.manual_score is not None:
                reviewed_convs.append(conv_map[conv_id])
                review_list.append((conv_map[conv_id], review))

        report.total_reviewed = len(review_list)

        if review_list:
            scores = [r.manual_score for _, r in review_list]
            report.avg_score = round(sum(scores) / len(scores), 1)

        agent_scores = defaultdict(list)
        agent_pass_count = defaultdict(lambda: [0, 0])
        for conv, review in review_list:
            agent_key = f"{conv.agent_name}({conv.agent_id})"
            final_score = review.manual_score if review.manual_score is not None else review.score
            agent_scores[agent_key].append(final_score)
            agent_pass_count[agent_key][1] += 1
            if final_score >= self.SCORE_THRESHOLD_PASS:
                agent_pass_count[agent_key][0] += 1

        report.agent_scores = {
            agent: round(sum(scores) / len(scores), 1)
            for agent, scores in agent_scores.items()
        }

        problem_counts = defaultdict(int)
        for _, review in review_list:
            for v in review.violations:
                problem_counts[v.rule_type.value] += 1
            for label in review.labels:
                problem_counts[f"标签:{label}"] += 1
        report.problem_counts = dict(problem_counts)

        report.training_list = self._identify_training_candidates(
            agent_scores, agent_pass_count
        )

        report.excellent_cases = self._identify_excellent_cases(review_list)
        report.rectification_items = self._generate_rectification_items(review_list)

        return report

    def _identify_training_candidates(
        self,
        agent_scores: Dict[str, List[float]],
        agent_pass_count: Dict[str, List[int]]
    ) -> List[str]:
        candidates = []
        for agent, scores in agent_scores.items():
            if len(scores) >= self.MIN_SAMPLES_FOR_TRAINING:
                avg_score = sum(scores) / len(scores)
                passed, total = agent_pass_count.get(agent, [0, len(scores)])
                pass_rate = passed / total if total > 0 else 0
                if avg_score < self.SCORE_THRESHOLD_ATTENTION or pass_rate < self.PASS_RATE_FOR_TRAINING:
                    candidates.append(agent)
        return candidates

    def _identify_excellent_cases(
        self,
        review_list: List
    ) -> List[str]:
        cases = []
        for conv, review in review_list:
            if review.is_excellent:
                score = review.manual_score if review.manual_score is not None else review.score
                cases.append(f"{conv.agent_name}-会话{conv.conv_id}(得分:{score})")
        return cases

    def _generate_rectification_items(
        self,
        review_list: List
    ) -> List[Dict]:
        items = []
        for conv, review in review_list:
            score = review.manual_score if review.manual_score is not None else review.score
            if score < self.SCORE_THRESHOLD_PASS:
                issues = [v.description for v in review.violations]
                items.append({
                    '客服': conv.agent_name,
                    '客服ID': conv.agent_id,
                    '会话ID': conv.conv_id,
                    '得分': score,
                    '主要问题': '; '.join(issues) if issues else '综合评分低于合格线',
                    '整改建议': self._get_rectification_suggestion(review),
                    '复核备注': review.reviewer_notes
                })
        return sorted(items, key=lambda x: x['得分'])

    def _get_rectification_suggestion(self, review: ReviewResult) -> str:
        suggestions = []
        rule_suggestions = {
            RuleType.TIMEOUT_REPLY.value: "加强响应速度培训，设置消息提醒机制",
            RuleType.NO_GREETING.value: "强化服务礼仪规范，练习开场话术",
            RuleType.VAGUE_PROMISE.value: "培训确定性表达技巧，避免模糊承诺",
            RuleType.FORBIDDEN_WORDS.value: "加强服务意识教育，严格规范服务用语",
            RuleType.NO_SOLUTION.value: "培训问题处理流程，确保每次沟通都有明确解决方案",
        }
        for v in review.violations:
            if v.rule_type.value in rule_suggestions:
                suggestions.append(rule_suggestions[v.rule_type.value])

        if not suggestions and review.manual_score is not None and review.manual_score < 80:
            suggestions.append("进行全面服务规范再培训，重点提升综合服务能力")

        return '；'.join(suggestions) if suggestions else "持续跟进观察"

    def export_to_excel(
        self,
        report: QualityReport,
        output_path: str,
        conversations: List[Conversation] = None,
        reviews: Dict[str, ReviewResult] = None
    ) -> bool:
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                summary_data = [{
                    '报告日期': report.report_date,
                    '抽样总数': report.total_sampled,
                    '已复核数': report.total_reviewed,
                    '平均得分': report.avg_score,
                    '合格率(%)': round(
                        sum(1 for s in report.agent_scores.values() if s >= self.SCORE_THRESHOLD_PASS) /
                        max(len(report.agent_scores), 1) * 100, 1
                    ) if report.agent_scores else 0,
                }]
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='报告概览', index=False)

                agent_df = pd.DataFrame([
                    {'客服': k, '平均得分': v, '是否合格': '是' if v >= self.SCORE_THRESHOLD_PASS else '否'}
                    for k, v in sorted(report.agent_scores.items(), key=lambda x: x[1])
                ])
                agent_df.to_excel(writer, sheet_name='个人得分', index=False)

                problem_df = pd.DataFrame([
                    {'问题类型': k, '出现次数': v}
                    for k, v in sorted(report.problem_counts.items(), key=lambda x: x[1], reverse=True)
                ])
                problem_df.to_excel(writer, sheet_name='常见问题', index=False)

                training_df = pd.DataFrame([{'待培训客服': x} for x in report.training_list])
                training_df.to_excel(writer, sheet_name='待培训名单', index=False)

                excellent_df = pd.DataFrame([{'优秀案例': x} for x in report.excellent_cases])
                excellent_df.to_excel(writer, sheet_name='优秀案例', index=False)

                rect_df = pd.DataFrame(report.rectification_items)
                rect_df.to_excel(writer, sheet_name='整改清单', index=False)

                if conversations and reviews:
                    detail_rows = []
                    conv_map = {c.conv_id: c for c in conversations}
                    for conv_id, review in reviews.items():
                        conv = conv_map.get(conv_id)
                        if conv:
                            detail_rows.append({
                                '会话ID': conv_id,
                                '客服': conv.agent_name,
                                '店铺': conv.shop,
                                '班次': conv.shift.value,
                                '订单状态': conv.order_status.value,
                                '系统评分': review.score,
                                '人工评分': review.manual_score if review.manual_score is not None else '',
                                '违规项数': len(review.violations),
                                '标签': ', '.join(review.labels),
                                '优秀案例': '是' if review.is_excellent else '否',
                                '复核人': review.reviewed_by,
                                '复核时间': review.review_time.strftime('%Y-%m-%d %H:%M') if review.review_time else '',
                                '复核备注': review.reviewer_notes
                            })
                    pd.DataFrame(detail_rows).to_excel(writer, sheet_name='复核明细', index=False)

            return True
        except Exception as e:
            print(f"导出失败: {e}")
            return False

    def get_problem_summary_text(self, report: QualityReport) -> str:
        lines = [
            f"质检报告 - {report.report_date}",
            "=" * 50,
            f"抽样总数: {report.total_sampled}",
            f"已复核数: {report.total_reviewed}",
            f"平均得分: {report.avg_score}",
            "",
        ]
        if report.problem_counts:
            lines.append("常见问题TOP10:")
            sorted_problems = sorted(report.problem_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            for p, c in sorted_problems:
                lines.append(f"  {p}: {c}次")
            lines.append("")

        if report.training_list:
            lines.append(f"待培训名单({len(report.training_list)}人):")
            lines.extend([f"  - {t}" for t in report.training_list])
            lines.append("")

        if report.excellent_cases:
            lines.append(f"优秀案例({len(report.excellent_cases)}个):")
            lines.extend([f"  - {e}" for e in report.excellent_cases])

        return "\n".join(lines)
