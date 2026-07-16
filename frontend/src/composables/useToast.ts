import { ref, type Ref } from 'vue'

interface ToastOptions {
  message: string
  type?: 'success' | 'warning' | 'error' | 'info'
  duration?: number
}

interface ToastItem {
  id: number
  message: string
  type: 'success' | 'warning' | 'error' | 'info'
}

const toasts: Ref<ToastItem[]> = ref([])
let nextId = 0

export function useToast() {
  function showToast(options: ToastOptions) {
    const id = nextId++
    const item: ToastItem = {
      id,
      message: options.message,
      type: options.type || 'info',
    }
    toasts.value.push(item)
    setTimeout(() => {
      removeToast(id)
    }, options.duration || 3000)
  }

  function removeToast(id: number) {
    const index = toasts.value.findIndex((t) => t.id === id)
    if (index !== -1) {
      toasts.value.splice(index, 1)
    }
  }

  return { toasts, showToast, removeToast }
}
