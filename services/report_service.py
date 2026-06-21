from typing import List, Dict, Optional
from collections import defaultdict
from datetime import datetime
import os

import pandas as pd

from models import Conversation, ReviewResult, QualityReport, Agent, RuleType
from services.config_manager import ConfigManager


class ReportService:
    def __init__(self):
        self._reload_config()

    def _reload_config(self):
        cfg = ConfigManager().get_config()
        self.SCORE_THRESHOLD_PASS = cfg.score_threshold_pass
        self.SCORE_THRESHOLD_ATTENTION = cfg.score_threshold_attention
        self.MIN_SAMPLES_FOR_TRAINING = cfg.min_samples_for_training
        self.PASS_RATE_FOR_TRAINING = cfg.pass_rate_for_training

    def generate_report(
        self,
        sampled_conversations: List[Conversation],
        reviews: Dict[str, ReviewResult],
        agents: List[Agent],
        report_date: Optional[str] = None,
        prefer_manual_score: bool = True
    ) -> QualityReport:
        self._reload_config()

        if report_date is None:
            report_date = datetime.now().strftime("%Y-%m-%d")

        report = QualityReport(report_date=report_date)
        report.total_sampled = len(sampled_conversations)

        conv_map = {c.conv_id: c for c in sampled_conversations}
        all_reviews = []
        for conv in sampled_conversations:
            review = reviews.get(conv.conv_id)
            if review:
                all_reviews.append((conv, review))

        manually_reviewed = [(c, r) for c, r in all_reviews if r.manual_score is not None]
        report.total_reviewed = len(manually_reviewed)

        def get_final_score(review: ReviewResult) -> float:
            if prefer_manual_score and review.manual_score is not None:
                return review.manual_score
            return review.score

        if all_reviews:
            scores = [get_final_score(r) for _, r in all_reviews]
            report.avg_score = round(sum(scores) / len(scores), 1)

        agent_scores = defaultdict(list)
        agent_pass_count = defaultdict(lambda: [0, 0])
        for conv, review in all_reviews:
            agent_key = f"{conv.agent_name}({conv.agent_id})"
            final_score = get_final_score(review)
            agent_scores[agent_key].append(final_score)
            agent_pass_count[agent_key][1] += 1
            if final_score >= self.SCORE_THRESHOLD_PASS:
                agent_pass_count[agent_key][0] += 1

        report.agent_scores = {
            agent: round(sum(scores) / len(scores), 1)
            for agent, scores in agent_scores.items()
        }

        problem_counts = defaultdict(int)
        for _, review in all_reviews:
            for v in review.violations:
                problem_counts[v.rule_type.value] += 1
            for label in review.labels:
                problem_counts[f"标签:{label}"] += 1
        report.problem_counts = dict(problem_counts)

        report.training_list = self._identify_training_candidates(
            agent_scores, agent_pass_count
        )

        report.excellent_cases = self._identify_excellent_cases(all_reviews, get_final_score)
        report.rectification_items = self._generate_rectification_items(all_reviews, get_final_score)

        report.report_mode = "人工复核口径" if prefer_manual_score else "自动规则口径"
        report.final_score_map = {
            c.conv_id: get_final_score(reviews.get(c.conv_id, ReviewResult(conv_id=c.conv_id)))
            for c in sampled_conversations
        }

        rule_set_breakdown = defaultdict(lambda: {
            'count': 0,
            'reviewed': 0,
            'avg_score': 0.0,
            'scores': [],
            'problems': defaultdict(int),
            'agent_scores': defaultdict(list),
            'agent_pass_count': defaultdict(lambda: [0, 0]),
            'training_list': [],
        })
        for conv, review in all_reviews:
            rs_id = getattr(review, 'rule_set_id', 'default')
            rs_version = getattr(review, 'rule_set_version', '1.0')
            key = f"{rs_id}_v{rs_version}"
            bd = rule_set_breakdown[key]
            bd['count'] += 1
            if review.manual_score is not None:
                bd['reviewed'] += 1
            final_score = get_final_score(review)
            bd['scores'].append(final_score)
            bd['agent_scores'][conv.agent_name].append(final_score)
            if final_score >= self.SCORE_THRESHOLD_PASS:
                bd['agent_pass_count'][conv.agent_name][0] += 1
            bd['agent_pass_count'][conv.agent_name][1] += 1
            for v in review.violations:
                bd['problems'][v.rule_type.value] += 1

        for key, bd in rule_set_breakdown.items():
            if bd['scores']:
                bd['avg_score'] = round(sum(bd['scores']) / len(bd['scores']), 1)
            bd['agent_scores'] = {
                agent: round(sum(scores) / len(scores), 1)
                for agent, scores in bd['agent_scores'].items()
            }
            rs_training = []
            for agent, scores in bd['agent_scores'].items():
                passed, total = bd['agent_pass_count'].get(agent, [0, len(bd['scores'])])
                if total >= self.MIN_SAMPLES_FOR_TRAINING:
                    avg = bd['agent_scores'][agent]
                    pass_rate = passed / total if total > 0 else 0
                    if avg < self.SCORE_THRESHOLD_ATTENTION or pass_rate < self.PASS_RATE_FOR_TRAINING:
                        rs_training.append(f"{agent}(平均分:{avg},合格率:{int(pass_rate*100)}%)")
            bd['training_list'] = rs_training
            bd['problems'] = dict(bd['problems'])
            del bd['scores']
            del bd['agent_pass_count']

        report.rule_set_breakdown = dict(rule_set_breakdown)

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
        review_list: List,
        score_getter
    ) -> List[str]:
        cases = []
        for conv, review in review_list:
            if review.is_excellent:
                score = score_getter(review)
                cases.append(f"{conv.agent_name}-会话{conv.conv_id}(得分:{score})")
        return cases

    def _generate_rectification_items(
        self,
        review_list: List,
        score_getter
    ) -> List[Dict]:
        items = []
        for conv, review in review_list:
            score = score_getter(review)
            if score < self.SCORE_THRESHOLD_PASS:
                issues = [v.description for v in review.violations]
                items.append({
                    '客服': conv.agent_name,
                    '客服ID': conv.agent_id,
                    '会话ID': conv.conv_id,
                    '得分': score,
                    '主要问题': '; '.join(issues) if issues else '综合评分低于合格线',
                    '整改建议': self._get_rectification_suggestion(review, score),
                    '复核备注': review.reviewer_notes
                })
        return sorted(items, key=lambda x: x['得分'])

    def _get_rectification_suggestion(self, review: ReviewResult, final_score: float = None) -> str:
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

        if not suggestions:
            if review.manual_score is not None and review.manual_score < 80:
                suggestions.append("进行全面服务规范再培训，重点提升综合服务能力")
            elif final_score is not None and final_score < 80:
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
                    '报告口径': getattr(report, 'report_mode', '人工复核口径'),
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

                rule_set_breakdown = getattr(report, 'rule_set_breakdown', {})
                if rule_set_breakdown:
                    rs_rows = []
                    for rs_key, bd in rule_set_breakdown.items():
                        top_problems = sorted(bd['problems'].items(), key=lambda x: x[1], reverse=True)[:5]
                        problems_text = '; '.join([f"{k}({v}次)" for k, v in top_problems])
                        training_text = '; '.join(bd['training_list']) if bd['training_list'] else '无'
                        pass_count = sum(1 for s in bd['agent_scores'].values() if s >= self.SCORE_THRESHOLD_PASS)
                        pass_rate = round(pass_count / max(len(bd['agent_scores']), 1) * 100, 1)
                        rs_rows.append({
                            '规则集/版本': rs_key,
                            '样本数': bd['count'],
                            '已复核数': bd['reviewed'],
                            '平均得分': bd['avg_score'],
                            '合格率(%)': pass_rate,
                            '涉及客服数': len(bd['agent_scores']),
                            '常见问题TOP5': problems_text,
                            '待培训客服': training_text,
                        })
                    pd.DataFrame(rs_rows).to_excel(writer, sheet_name='规则版本汇总', index=False)

                if conversations and reviews:
                    detail_rows = []
                    conv_map = {c.conv_id: c for c in conversations}
                    final_scores = getattr(report, 'final_score_map', {})
                    for conv_id, review in reviews.items():
                        conv = conv_map.get(conv_id)
                        if conv:
                            final_score = final_scores.get(conv_id, review.score)
                            rs_id = getattr(review, 'rule_set_id', 'default')
                            rs_version = getattr(review, 'rule_set_version', '1.0')
                            detail_rows.append({
                                '会话ID': conv_id,
                                '客服': conv.agent_name,
                                '店铺': conv.shop,
                                '班次': conv.shift.value,
                                '订单状态': conv.order_status.value,
                                '规则集': '默认规则' if rs_id == 'default' else rs_id,
                                '规则版本': rs_version,
                                '系统评分': review.score,
                                '人工评分': review.manual_score if review.manual_score is not None else '',
                                '最终得分': final_score,
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
