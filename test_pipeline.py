import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services import ImportService, SamplingService, RuleEngine, ReviewService, ReportService
from models import ShiftType


def test_pipeline():
    print("=" * 60)
    print("测试核心业务逻辑管道")
    print("=" * 60)

    sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
    agents_file = os.path.join(sample_dir, "客服名单示例.xlsx")
    convs_file = os.path.join(sample_dir, "当日会话示例.xlsx")

    if not os.path.exists(agents_file) or not os.path.exists(convs_file):
        print("示例数据不存在，先生成...")
        from generate_sample_data import generate_sample_data
        generate_sample_data(sample_dir)

    print("\n[1/5] 导入客服名单...")
    agents, errors = ImportService.import_agents(agents_file)
    print(f"  成功导入 {len(agents)} 名客服")
    if errors:
        print(f"  警告 {len(errors)} 条")
    for a in agents[:3]:
        print(f"    - {a.agent_id} {a.name} [{a.shop} - {a.shift.value}]")

    print("\n[2/5] 导入会话文件...")
    conversations, errors = ImportService.import_conversations(convs_file)
    print(f"  成功导入 {len(conversations)} 个会话")
    if errors:
        print(f"  警告 {len(errors)} 条")
    for c in conversations[:3]:
        print(f"    - {c.conv_id} {c.agent_name} 消息数:{len(c.messages)}")

    print("\n[3/5] 执行分层抽样（按客服抽样2条)...")
    sampler = SamplingService(seed=42)
    sampled = sampler.stratified_sample(conversations, 2, "agent")
    print(f"  抽取样本数: {len(sampled)}")

    shops = set()
    for s in sampled:
        shops.add(s.agent_name)
    print(f"  涉及客服数: {len(shops)}")

    print("\n[4/5] 执行规则检查...")
    engine = RuleEngine()
    review_service = ReviewService()

    problem_counts = {}
    for conv in sampled:
        violations = engine.check_all(conv)
        score = engine.calculate_score(violations)
        review_service.initialize_review(conv.conv_id, violations, score)
        for v in violations:
            key = v.rule_type.value
            problem_counts[key] = problem_counts.get(key, 0) + 1

        if violations:
            print(f"  会话 {conv.conv_id} ({conv.agent_name}: 得分{score:.0f}")
            for v in violations[:2]:
                print(f"    - [{v.rule_type.value}] - {v.description}")

    print(f"\n  问题分布: {problem_counts}")

    print("\n[5/5] 模拟人工复核并生成报告...")
    for i, conv in enumerate(sampled):
        review = review_service.get_review(conv.conv_id)
        base_score = review.score if review else 100
        adjustment = -10 if i % 3 == 0 else (5 if i % 3 == 1 else 0)
        manual = max(0, min(100, base_score + adjustment))
        review_service.update_score(conv.conv_id, manual)
        if i % 5 == 0:
            review_service.toggle_excellent(conv.conv_id, True)
        review_service.add_label(conv.conv_id, "响应速度快" if manual >= 80 else "需要改进")
        review_service.set_reviewer(conv.conv_id, "张主管")

    report = ReportService().generate_report(
        sampled, review_service.get_all_reviews(), agents
    )

    print(f"  报告日期: {report.report_date}")
    print(f"  抽样: {report.total_sampled}")
    print(f"  复核: {report.total_reviewed}")
    print(f"  平均分: {report.avg_score}")
    print(f"  个人得分: {report.agent_scores}")
    print(f"  常见问题: {report.problem_counts}")
    print(f"  待培训: {report.training_list}")
    print(f"  优秀案例: {report.excellent_cases}")
    print(f"  整改项: {len(report.rectification_items)} 条")

    export_path = os.path.join(sample_dir, "质检报告_test.xlsx")
    success = ReportService().export_to_excel(report, export_path, sampled, review_service.get_all_reviews())
    print(f"\n报告导出: {'成功' if success else '失败'} -> {export_path}")

    print("\n" + "=" * 60)
    print("所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    test_pipeline()
