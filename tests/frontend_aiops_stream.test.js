const assert = require('assert');

const AIOpsStream = require('../static/aiopsStream.js');

const title = AIOpsStream.createSessionTitle(new Date('2026-07-18T15:28:00+08:00'));
assert.strictEqual(title, 'AI Ops 诊断 07-18 15:28');

let state = AIOpsStream.createState();
state = AIOpsStream.applyEvent(state, {
    type: 'plan',
    message: '执行计划已制定，共 2 个步骤',
    plan: ['查询当前告警', '分析相关日志']
});
state = AIOpsStream.applyEvent(state, {
    type: 'step_complete',
    message: '步骤执行完成 (1/2)：查询当前告警',
    current_step: '查询当前告警',
    current_step_index: 1,
    total_steps: 2
});
state = AIOpsStream.applyEvent(state, {
    type: 'status',
    message: 'Planner Agent 复核完成，转交报告 Agent'
});

assert.match(state.content, /## 📋 执行计划\n\n执行计划已制定/);
assert.match(state.content, /1\. 查询当前告警/);
assert.match(state.content, /2\. 分析相关日志/);
assert.match(state.content, /\n\n- ✅ 步骤执行完成 \(1\/2\)：查询当前告警\n\n/);
assert.match(state.content, /- ⏳ Planner Agent 复核完成/);

state = AIOpsStream.applyEvent(state, { type: 'report_chunk', data: '# 故障' });
state = AIOpsStream.applyEvent(state, { type: 'report_chunk', data: '诊断报告' });
const streamedContent = state.content;
state = AIOpsStream.applyEvent(state, {
    type: 'report',
    report: '# 故障诊断报告'
});

assert.strictEqual(state.content, streamedContent);
assert.strictEqual((state.content.match(/## 🎯 诊断报告/g) || []).length, 1);
assert.match(state.content, /# 故障诊断报告/);

state = AIOpsStream.applyEvent(state, { type: 'complete' });
assert.strictEqual(state.done, true);

console.log('frontend AI Ops stream tests passed');
