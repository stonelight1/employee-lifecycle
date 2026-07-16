import { ref } from 'vue'

interface ConfirmOptions {
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
  onConfirm: () => void | Promise<void>
}

export function useConfirm() {
  const show = ref(false)
  const loading = ref(false)
  const options = ref<ConfirmOptions>({
    title: '',
    message: '',
    confirmText: '确认',
    cancelText: '取消',
    danger: false,
    onConfirm: () => {},
  })

  function confirm(opts: ConfirmOptions) {
    options.value = { ...opts }
    show.value = true
  }

  async function handleConfirm() {
    loading.value = true
    try {
      await options.value.onConfirm()
      show.value = false
    } catch {
      // error handled by caller
    } finally {
      loading.value = false
    }
  }

  function handleCancel() {
    show.value = false
  }

  return { show, loading, options, confirm, handleConfirm, handleCancel }
}
