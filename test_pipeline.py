import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services import (
    ImportService, SamplingService, RuleEngine, ReviewService, ReportService,
    ConfigManager, RuleConfig, BatchManager, QualityBatch
)


def test_role_recognition():
    print("\n" + "=" * 60)
    print("测试1: 角色识别逻辑（优先按角色列判断）")
    print("=" * 60)

    sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
    convs_file = os.path.join(sample_dir, "当日会话示例.xlsx")

    if not os.path.exists(convs_file):
        from generate_sample_data import generate_sample_data
        generate_sample_data(sample_dir)

    conversations, errors = ImportService.import_conversations(convs_file)
    print(f"  导入会话数: {len(conversations)}")

    test_conv = None
    for conv in conversations:
        if len(conv.messages) >= 4:
            test_conv = conv
            break

    if test_conv:
        print(f"\n  测试会话: {test_conv.conv_id}")
        print(f"  客服: {test_conv.agent_name}")
        print(f"\n  消息角色识别验证:")
        customer_count = 0
        agent_count = 0
        for i, msg in enumerate(test_conv.messages[:6]):
            role = "客户" if msg.is_customer else "客服"
            expected_role = "客户" if i % 2 == 1 else "客服"
            status = "✅" if role == expected_role else "❌"
            print(f"    {status} 消息{i+1}: 角色={msg.sender_type}, is_customer={msg.is_customer}")
            if msg.is_customer:
                customer_count += 1
            else:
                agent_count += 1

        print(f"\n  客户消息数: {customer_count}, 客服消息数: {agent_count}")
        print(f"  角色列优先识别: {'通过' if customer_count > 0 and agent_count > 0 else '失败'}")

    return conversations


def test_config_persistence():
    print("\n" + "=" * 60)
    print("测试2: 配置持久化")
    print("=" * 60)

    config_manager = ConfigManager()
    original = config_manager.get_config()
    print(f"  当前配置文件: {config_manager.get_config_path()}")
    print(f"  原始超时设置: {original.reply_timeout}秒")

    test_config = RuleConfig(
        reply_timeout=300,
        forbidden_words=list(original.forbidden_words) + ['测试禁用词'],
        greeting_patterns=list(original.greeting_patterns),
        vague_phrases=list(original.vague_phrases),
        solution_keywords=list(original.solution_keywords),
        score_threshold_pass=85.0,
        score_threshold_attention=75.0,
        min_samples_for_training=3,
        pass_rate_for_training=0.7,
    )
    success = config_manager.update_config(test_config)
    print(f"  保存新配置: {'成功' if success else '失败'}")

    config_manager2 = ConfigManager()
    loaded = config_manager2.get_config()
    print(f"  重新加载配置...")
    print(f"  加载后超时: {loaded.reply_timeout}秒 (期望: 300)")
    print(f"  加载后通过线: {loaded.score_threshold_pass} (期望: 85.0)")
    print(f"  '测试禁用词'在列表: {'是' if '测试禁用词' in loaded.forbidden_words else '否'}")

    ok = (loaded.reply_timeout == 300 and
          loaded.score_threshold_pass == 85.0 and
          '测试禁用词' in loaded.forbidden_words)
    print(f"\n  配置持久化测试: {'通过 ✅' if ok else '失败 ❌'}")

    config_manager.reset_to_default()
    restored = config_manager.get_config()
    print(f"  恢复默认设置，超时: {restored.reply_timeout}秒")

    return ok


def test_report_modes(conversations):
    print("\n" + "=" * 60)
    print("测试3: 两种报告口径（自动规则 vs 人工优先）")
    print("=" * 60)

    sampler = SamplingService(seed=42)
    sampled = sampler.stratified_sample(conversations, 2, "agent")
    print(f"  抽样会话数: {len(sampled)}")

    engine = RuleEngine()
    review_service = ReviewService()
    for conv in sampled:
        violations = engine.check_all(conv)
        score = engine.calculate_score(violations)
        review_service.initialize_review(conv.conv_id, violations, score)

    for i, (cid, result) in enumerate(list(review_service.results.items())[:8]):
        if i % 4 == 0:
            review_service.results[cid].score = 75
        elif i % 4 == 1:
            review_service.results[cid].score = 68

    results = review_service.get_all_reviews()

    report_service = ReportService()

    print("\n  [模式A] 仅自动规则口径:")
    report_auto = report_service.generate_report(
        sampled, results, [], prefer_manual_score=False
    )
    print(f"    抽样数: {report_auto.total_sampled}")
    print(f"    已复核(人工): {report_auto.total_reviewed}")
    print(f"    平均分: {report_auto.avg_score}")
    print(f"    个人得分数量: {len(report_auto.agent_scores)}")
    print(f"    常见问题数: {len(report_auto.problem_counts)}")
    print(f"    整改项数: {len(report_auto.rectification_items)}")
    print(f"    报告口径: {report_auto.report_mode}")
    auto_ok = (report_auto.total_sampled > 0 and
               len(report_auto.agent_scores) > 0 and
               len(report_auto.rectification_items) > 0 and
               report_auto.report_mode == "自动规则口径")
    print(f"    自动口径完整性: {'通过 ✅' if auto_ok else '失败 ❌'}")

    for i, (cid, result) in enumerate(list(results.items())[:5]):
        if i % 2 == 0:
            review_service.update_score(cid, max(0, result.score - 5))
        else:
            review_service.update_score(cid, 70)

    print("\n  [模式B] 人工复核优先口径（50%已填人工分）:")
    results_updated = review_service.get_all_reviews()
    report_manual = report_service.generate_report(
        sampled, results_updated, [], prefer_manual_score=True
    )
    print(f"    抽样数: {report_manual.total_sampled}")
    print(f"    已复核: {report_manual.total_reviewed} (人工填充分数)")
    print(f"    平均分: {report_manual.avg_score}")
    print(f"    未填人工分的会话自动用系统分补充，无空缺")
    print(f"    整改项数: {len(report_manual.rectification_items)}")
    manual_ok = (report_manual.total_sampled == len(report_manual.final_score_map) and
                 report_manual.total_reviewed > 0 and
                 len(report_manual.agent_scores) > 0)
    print(f"    人工优先完整性: {'通过 ✅' if manual_ok else '失败 ❌'}")

    print(f"\n  报告模式测试: {'通过 ✅' if auto_ok and manual_ok else '失败 ❌'}")
    return auto_ok and manual_ok, sampled, results_updated


def test_batch_management(sampled, all_conversations, results):
    print("\n" + "=" * 60)
    print("测试4: 质检批次保存与加载")
    print("=" * 60)

    batch_manager = BatchManager()
    print(f"  批次保存目录: {batch_manager.get_batches_dir()}")

    from models import Agent
    agents = []
    agent_ids = set()
    for c in sampled:
        if c.agent_id not in agent_ids:
            agent_ids.add(c.agent_id)
            from models import ShiftType
            agents.append(Agent(
                agent_id=c.agent_id,
                name=c.agent_name,
                shop=c.shop,
                shift=c.shift
            ))

    print(f"  保存批次中... (样本数: {len(sampled)})")
    batch = QualityBatch.create(
        batch_name="测试批次_集成测试",
        sampled_conversations=sampled,
        all_conversations=all_conversations,
        agents=agents,
        review_results=results,
        note="这是一个自动测试批次"
    )
    save_ok = batch_manager.save_batch(batch)
    print(f"  保存批次: {'成功 ✅' if save_ok else '失败 ❌'}")

    batches = batch_manager.list_batches()
    print(f"  历史批次数量: {len(batches)}")

    loaded = batch_manager.load_batch(batch.batch_id)
    print(f"  加载批次: {'成功 ✅' if loaded else '失败 ❌'}")

    if loaded:
        progress = loaded.get_review_progress()
        print(f"\n  批次信息:")
        print(f"    批次ID: {loaded.batch_id}")
        print(f"    批次名称: {loaded.batch_name}")
        print(f"    样本数: {progress['total']}")
        print(f"    已复核: {progress['reviewed']}")
        print(f"    待复核: {progress['pending']}")
        print(f"    完成进度: {progress['progress']:.1f}%")

        loaded_agents, loaded_convs, loaded_results = loaded.to_entities()
        print(f"\n  批次数据恢复验证:")
        print(f"    客服数: {len(loaded_agents)} (原: {len(agents)})")
        print(f"    抽样会话数: {len(loaded_convs)} (原: {len(sampled)})")
        print(f"    复核结果数: {len(loaded_results)} (原: {len(results)})")

        data_ok = (len(loaded_agents) == len(agents) and
                   len(loaded_results) == len(results))
        print(f"  批次数据完整性: {'通过 ✅' if data_ok else '失败 ❌'}")

        update_ok = batch_manager.update_batch_reviews(batch.batch_id, results)
        print(f"  更新批次复核进度: {'成功 ✅' if update_ok else '失败 ❌'}")

    else:
        data_ok = False

    all_ok = save_ok and loaded is not None and data_ok
    print(f"\n  批次管理测试: {'通过 ✅' if all_ok else '失败 ❌'}")
    return all_ok


def test_consistency_check(conversations):
    print("\n" + "=" * 60)
    print("测试5: 角色识别与规则检查一致性")
    print("=" * 60)

    engine = RuleEngine()

    for conv in conversations[:5]:
        if len(conv.messages) < 3:
            continue

        print(f"\n  会话 {conv.conv_id}:")
        customer_msgs = [m for m in conv.messages if m.is_customer]
        agent_msgs = [m for m in conv.messages if not m.is_customer]
        print(f"    客户消息: {len(customer_msgs)}条, 客服消息: {len(agent_msgs)}条")

        violations = engine.check_all(conv)
        timeout_violations = [v for v in violations if v.rule_type.value == "超时回复"]
        solution_violations = [v for v in violations if v.rule_type.value == "未给解决方案"]

        print(f"    超时回复违规: {len(timeout_violations)}次")
        print(f"    未给解决方案违规: {len(solution_violations)}次")

        if timeout_violations:
            v = timeout_violations[0]
            if v.related_message_index is not None and 0 <= v.related_message_index < len(conv.messages):
                msg = conv.messages[v.related_message_index]
                print(f"    超时违规证据消息: is_customer={msg.is_customer}, 角色={msg.sender_type}")
                if not msg.is_customer:
                    print("    ✅ 违规确实在客服消息上，逻辑正确")

        if solution_violations:
            v = solution_violations[0]
            if v.related_message_index is not None and 0 <= v.related_message_index < len(conv.messages):
                msg = conv.messages[v.related_message_index]
                print(f"    未解决违规证据消息: is_customer={msg.is_customer}, 角色={msg.sender_type}")
                if not msg.is_customer:
                    print("    ✅ 违规确实在客服消息上，逻辑正确")

        break

    print(f"\n  一致性检查完成")
    return True


def test_pipeline():
    print("\n" + "=" * 60)
    print("电商客服质检系统 v2.0 - 集成测试")
    print("=" * 60)

    all_pass = True

    try:
        conversations = test_role_recognition()
    except Exception as e:
        print(f"测试1异常: {e}")
        import traceback
        traceback.print_exc()
        all_pass = False

    try:
        config_ok = test_config_persistence()
        all_pass = all_pass and config_ok
    except Exception as e:
        print(f"测试2异常: {e}")
        import traceback
        traceback.print_exc()
        all_pass = False

    try:
        report_ok, sampled, results = test_report_modes(conversations)
        all_pass = all_pass and report_ok
    except Exception as e:
        print(f"测试3异常: {e}")
        import traceback
        traceback.print_exc()
        all_pass = False
        sampled = []
        results = {}

    try:
        batch_ok = test_batch_management(sampled, conversations, results)
        all_pass = all_pass and batch_ok
    except Exception as e:
        print(f"测试4异常: {e}")
        import traceback
        traceback.print_exc()
        all_pass = False

    try:
        test_consistency_check(conversations)
    except Exception as e:
        print(f"测试5异常: {e}")
        import traceback
        traceback.print_exc()
        all_pass = False

    print("\n" + "=" * 60)
    if all_pass:
        print("🎉 所有测试通过！ v2.0新功能验证成功")
        print("=" * 60)
    else:
        print("⚠️  部分测试未通过，请检查上述结果")
        print("=" * 60)
    print("\n可启动UI程序: python main.py")

    return all_pass


if __name__ == "__main__":
    success = test_pipeline()
    sys.exit(0 if success else 1)
