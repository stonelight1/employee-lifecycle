<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post, put, patch } from '@/api'
import { useToast } from '@/composables/useToast'
import BaseModal from '@/components/base/BaseModal.vue'
import { getStatusLabel, communicationTypeMap, riskMap } from '@/constants/status'
import type { CommunicationItem, AiSummaryItem, RiskAssessmentItem, TextVersionItem } from '@/types'
import PageHeader from '@/components/layout/PageHeader.vue'
import BaseButton from '@/components/base/BaseButton.vue'

const route = useRoute()
const router = useRouter()
const commId = Number(route.params.id)
const { showToast } = useToast()

const communication = ref<CommunicationItem | null>(null)
const aiSummaries = ref<AiSummaryItem[]>([])
const riskAssessments = ref<RiskAssessmentItem[]>([])
const textVersions = ref<TextVersionItem[]>([])
const loading = ref(false)
const generatingAi = ref(false)
const showTextVersions = ref(false)
const showRiskReviewModal = ref(false)
const reviewingRisk = ref(false)
const pendingRiskAction = ref<'confirm' | 'modify' | 'reject' | null>(null)
const riskReviewComment = ref('')

const activeAiSummary = computed(() => aiSummaries.value.find(a => a.is_current && !a.is_stale && a.summary_status === 'SUCCEEDED'))
const staleAiSummaries = computed(() => aiSummaries.value.filter(a => a.is_stale || a.summary_status !== 'SUCCEEDED'))

const currentRisk = computed(() => riskAssessments.value.find(r => r.is_current))

async function loadData() {
  loading.value = true
  try {
    const [commRes, aiRes, riskRes, verRes] = await Promise.all([
      get<CommunicationItem>(`/communications/${commId}`),
      get<{ items: AiSummaryItem[]; total: number }>(`/communications/${commId}/ai-summaries`),
      get<{ items: RiskAssessmentItem[]; total: number }>(`/communications/${commId}/risk-assessments`),
      get<{ items: TextVersionItem[]; total: number }>(`/communications/${commId}/text-versions`),
    ])
    if (commRes.success) communication.value = commRes.data!
    if (aiRes.success && aiRes.data) aiSummaries.value = aiRes.data.items
    if (riskRes.success && riskRes.data) riskAssessments.value = riskRes.data.items
    if (verRes.success && verRes.data) textVersions.value = verRes.data.items
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function generateAi() {
  if (!communication.value?.current_text_version_id) {
    showToast({ type: 'warning', message: '当前无文本版本，请先保存沟通文本' })
    return
  }
  if (communication.value.communication_status === 'DRAFT') {
    showToast({ type: 'warning', message: '草稿状态无法生成 AI，请先完成沟通记录' })
    return
  }
  generatingAi.value = true
  try {
    const res = await post(`/communications/${commId}/ai-summaries`, {
      source_text_version_id: communication.value.current_text_version_id,
      request_id: `req-${Date.now()}`,
    })
    if (res.success) {
      showToast({ type: 'success', message: 'AI 生成成功' })
      await loadData()
    }
  } catch (e: any) {
    showToast({ type: 'error', message: e.message || 'AI 生成失败' })
  } finally {
    generatingAi.value = false
  }
}

async function handleRiskReview(action: string) {
  if (!currentRisk.value) return
  pendingRiskAction.value = action as 'confirm' | 'modify' | 'reject'
  riskReviewComment.value = ''
  showRiskReviewModal.value = true
}

async function submitRiskReview() {
  if (!currentRisk.value || !pendingRiskAction.value) return
  const riskId = currentRisk.value.id
  reviewingRisk.value = true
  try {
    const url = '/risk-assessments/' + riskId + '/' + pendingRiskAction.value
    const res = await post(url, {
      hr_comment: riskReviewComment.value.trim() || null,
    })
    if (res.success) {
      showToast({ type: 'success', message: '操作成功' })
      showRiskReviewModal.value = false
      await loadData()
    }
  } catch (e: any) {
    showToast({ type: 'error', message: e.message || '操作失败' })
  } finally {
    reviewingRisk.value = false
  }
}

function parseSummary(summaryStr: string | undefined): any {
  if (!summaryStr) return null
  try { return JSON.parse(summaryStr) } catch { return null }
}

const statusLabels: Record<string, string> = {
  DRAFT: '草稿', COMPLETED: '已完成', VOIDED: '已作废',
  PROCESSING: '处理中', SUCCEEDED: '成功', FAILED: '失败', CANCELLED: '已取消',
  PENDING_REVIEW: '待审核', CONFIRMED: '已确认', MODIFIED: '已修改', REJECTED: '已驳回',
}

const riskActionLabels: Record<string, string> = {
  confirm: '确认风险建议',
  modify: '修改风险建议',
  reject: '驳回风险建议',
}

onMounted(loadData)
</script>

<template>
  <div v-if="communication" class="page">
    <PageHeader :title="`沟通记录 #${communication.id}`" subtitle="查看沟通文本、AI 建议和风险审核">
      <template #actions>
        <span class="tag">{{ statusLabels[communication.communication_status] || communication.communication_status }}</span>
        <BaseButton variant="secondary" @click="router.back()">返回</BaseButton>
      </template>
    </PageHeader>

    <!-- 基本信息 -->
    <div class="card">
      <div class="section-title">基本信息</div>
      <div class="info-grid">
        <div class="info-item"><label>类型</label><span>{{ getStatusLabel(communicationTypeMap, communication.communication_type) }}</span></div>
        <div class="info-item"><label>状态</label><span>{{ statusLabels[communication.communication_status] || communication.communication_status }}</span></div>
        <div class="info-item"><label>文本版本</label><span>v{{ communication.current_text_version_no || '-' }}</span></div>
        <div class="info-item"><label>文本哈希</label><span class="hash">{{ communication.current_text_hash?.slice(0, 16) || '-' }}...</span></div>
      </div>
      <div class="form-actions" style="margin-top: 12px;">
        <button class="btn btn-sm" @click="showTextVersions = !showTextVersions">
          {{ showTextVersions ? '隐藏' : '查看' }}文本历史 ({{ textVersions.length }})
        </button>
      </div>
    </div>

    <!-- 文本版本历史 -->
    <div class="card" v-if="showTextVersions && textVersions.length > 0">
      <div class="section-title">文本版本历史</div>
      <div v-for="v in textVersions" :key="v.id" class="version-item">
        <div class="version-header">
          <span class="tag tag-blue">v{{ v.version_no }}</span>
          <span class="version-meta">{{ v.created_at?.slice(0, 19) }} by {{ v.created_by || '-' }}</span>
          <span class="version-meta">长度: {{ v.text_length }}字</span>
          <span v-if="v.version_no === communication.current_text_version_no" class="tag tag-green">当前版本</span>
        </div>
        <div class="version-text">{{ v.text_content?.slice(0, 500) }}{{ v.text_content?.length > 500 ? '...' : '' }}</div>
        <div v-if="v.change_reason" class="version-reason">修改原因: {{ v.change_reason }}</div>
      </div>
    </div>

    <!-- AI 总结 -->
    <div class="card">
      <div class="section-title">
        AI 总结建议
        <button class="btn btn-primary btn-sm" :disabled="generatingAi || communication.communication_status === 'DRAFT'" @click="generateAi">
          {{ generatingAi ? '生成中...' : '生成 AI 建议' }}
        </button>
      </div>

      <!-- 当前 AI -->
      <div v-if="activeAiSummary" class="ai-section">
        <div class="ai-header">
          <span class="tag tag-green">AI 建议</span>
          <span class="version-meta">生成时间: {{ activeAiSummary.created_at?.slice(0, 19) }}</span>
          <span class="version-meta">版本: v{{ activeAiSummary.version_no }}</span>
        </div>

        <div v-if="parseSummary(activeAiSummary.structured_summary)" class="ai-content">
          <div class="ai-field" v-for="(val, key) in parseSummary(activeAiSummary.structured_summary)" :key="key">
            <label>{{ key }}</label>
            <div v-if="Array.isArray(val)">
              <div v-for="(item, i) in val" :key="i" class="ai-list-item">• {{ typeof item === 'object' ? JSON.stringify(item) : item }}</div>
            </div>
            <div v-else>{{ typeof val === 'object' ? JSON.stringify(val) : val }}</div>
          </div>
        </div>
        <div v-else class="empty">无法解析 AI 总结内容</div>
      </div>

      <div v-else-if="aiSummaries.length > 0" class="notice">当前 AI 基于旧文本或已过期，请重新生成</div>
      <div v-else class="empty">暂无 AI 总结，点击上方按钮生成</div>

      <!-- 过期 AI -->
      <div v-if="staleAiSummaries.length > 0" class="stale-section">
        <details>
          <summary>历史 AI 记录 ({{ staleAiSummaries.length }})</summary>
          <div v-for="ai in staleAiSummaries" :key="ai.id" class="stale-item">
            <span class="tag tag-gray">v{{ ai.version_no }}</span>
            <span class="tag">{{ statusLabels[ai.summary_status] || ai.summary_status }}</span>
            <span class="version-meta">{{ ai.created_at?.slice(0, 19) }}</span>
            <span v-if="ai.is_stale" class="tag tag-orange">已过期</span>
          </div>
        </details>
      </div>
    </div>

    <!-- 风险评估 -->
    <div class="card">
      <div class="section-title">风险评估</div>

      <div v-if="currentRisk" class="risk-section">
        <div class="risk-header">
          <span class="tag" :class="{
            'tag-green': currentRisk.risk_review_status === 'CONFIRMED',
            'tag-orange': currentRisk.risk_review_status === 'PENDING_REVIEW',
            'tag-red': currentRisk.risk_review_status === 'REJECTED',
            'tag-blue': currentRisk.risk_review_status === 'MODIFIED',
          }">{{ statusLabels[currentRisk.risk_review_status] }}</span>
          <span>来源: {{ currentRisk.assessment_source === 'AI' ? 'AI 建议' : '人工录入' }}</span>
          <span v-if="currentRisk.ai_risk_level" class="tag" :class="{
            'tag-green': currentRisk.ai_risk_level === 'LOW',
            'tag-orange': currentRisk.ai_risk_level === 'MEDIUM',
            'tag-red': currentRisk.ai_risk_level === 'HIGH',
            'tag-gray': currentRisk.ai_risk_level === 'UNSPECIFIED',
          }">AI 风险: {{ riskMap[currentRisk.ai_risk_level]?.label || currentRisk.ai_risk_level }}</span>
          <span v-if="currentRisk.hr_risk_level" class="tag" :class="{
            'tag-green': currentRisk.hr_risk_level === 'LOW',
            'tag-orange': currentRisk.hr_risk_level === 'MEDIUM',
            'tag-red': currentRisk.hr_risk_level === 'HIGH',
            'tag-gray': currentRisk.hr_risk_level === 'UNSPECIFIED',
          }">HR 风险: {{ riskMap[currentRisk.hr_risk_level]?.label || currentRisk.hr_risk_level }}</span>
        </div>

        <div v-if="currentRisk.ai_risk_reasons" class="risk-detail">
          <label>AI 风险原因:</label>
          <div>{{ currentRisk.ai_risk_reasons }}</div>
        </div>

        <div v-if="currentRisk.hr_comment" class="risk-detail">
          <label>HR 意见:</label>
          <div>{{ currentRisk.hr_comment }}</div>
        </div>

        <!-- 审核按钮 -->
        <div v-if="currentRisk.risk_review_status === 'PENDING_REVIEW' && currentRisk.assessment_source === 'AI'" class="form-actions risk-actions">
          <button class="btn btn-success btn-sm" @click="handleRiskReview('confirm')">确认</button>
          <button class="btn btn-warning btn-sm" @click="handleRiskReview('modify')">修改</button>
          <button class="btn btn-danger btn-sm" @click="handleRiskReview('reject')">驳回</button>
        </div>
      </div>

      <div v-else class="empty">暂无风险评估</div>
    </div>
  </div>
  <div v-else class="loading">加载中...</div>

  <BaseModal
    :show="showRiskReviewModal"
    :title="pendingRiskAction ? riskActionLabels[pendingRiskAction] : '审核风险建议'"
    :confirm-text="pendingRiskAction === 'reject' ? '确认驳回' : '提交'"
    cancel-text="取消"
    :danger="pendingRiskAction === 'reject'"
    :loading="reviewingRisk"
    @confirm="submitRiskReview"
    @cancel="showRiskReviewModal = false"
  >
    <template #message>
      <div class="review-modal-content">
        <p class="review-modal-tip">可填写本次审核意见，系统会随风险审核记录一并保存。</p>
        <label class="review-comment-label" for="risk-review-comment">审核意见</label>
        <textarea
          id="risk-review-comment"
          v-model="riskReviewComment"
          class="review-comment-input"
          rows="4"
          maxlength="500"
          placeholder="请输入审核意见（可选）"
        />
      </div>
    </template>
  </BaseModal>
</template>

<style scoped>
.card { background: #fff; border-radius: 8px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06); }
.section-title { font-size: 16px; font-weight: 600; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #ebeef5; display: flex; justify-content: space-between; align-items: center; }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.info-item label { display: block; font-size: 12px; color: #909399; }
.hash { font-family: monospace; font-size: 12px; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; background: #f4f4f5; color: #909399; }
.tag-green { background: #e1f3d8; color: #67c23a; }
.tag-red { background: #fef0f0; color: #f56c6c; }
.tag-orange { background: #faecd8; color: #e6a23c; }
.tag-blue { background: #d9ecff; color: #409eff; }
.tag-gray { background: #f4f4f5; color: #909399; }
.btn { padding: 6px 16px; border: 1px solid #dcdfe6; border-radius: 6px; background: #fff; cursor: pointer; font-size: 14px; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.btn-primary { background: #409eff; color: #fff; border-color: #409eff; }
.btn-success { background: #67c23a; color: #fff; border-color: #67c23a; }
.btn-warning { background: #e6a23c; color: #fff; border-color: #e6a23c; }
.btn-danger { background: #f56c6c; color: #fff; border-color: #f56c6c; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.empty { text-align: center; padding: 32px; color: #909399; }
.loading { text-align: center; padding: 48px; color: #909399; }
.notice { background: #fdf6ec; color: #e6a23c; padding: 12px; border-radius: 4px; font-size: 13px; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; }
.risk-actions { margin-top: 12px; padding-top: 12px; border-top: 1px solid #ebeef5; justify-content: flex-start; }

/* AI 内容 */
.ai-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.ai-content { background: #f9f9f9; border-radius: 6px; padding: 12px 16px; }
.ai-field { margin-bottom: 12px; }
.ai-field label { font-weight: 600; font-size: 13px; color: #606266; display: block; margin-bottom: 4px; text-transform: capitalize; }
.ai-list-item { font-size: 13px; color: #303133; margin-bottom: 2px; }
.version-meta { font-size: 12px; color: #909399; }

/* 文本版本 */
.version-item { padding: 12px; border-bottom: 1px solid #f5f5f5; }
.version-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.version-text { font-size: 13px; color: #303133; white-space: pre-wrap; background: #fafafa; padding: 8px 12px; border-radius: 4px; max-height: 120px; overflow-y: auto; }
.version-reason { font-size: 12px; color: #909399; margin-top: 4px; }
.stale-section { margin-top: 16px; padding-top: 12px; border-top: 1px solid #ebeef5; }
.stale-section details { cursor: pointer; }
.stale-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; }

/* 风险 */
.risk-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
.risk-detail { padding: 8px 12px; background: #f9f9f9; border-radius: 4px; margin-bottom: 8px; }
.risk-detail label { font-size: 12px; color: #909399; display: block; margin-bottom: 4px; }
.review-modal-content { display: flex; flex-direction: column; gap: 8px; }
.review-modal-tip { margin: 0; color: var(--color-text-secondary); }
.review-comment-label { font-size: 12px; color: var(--color-text-secondary); }
.review-comment-input {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font: inherit;
  resize: vertical;
}
.review-comment-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}
</style>
