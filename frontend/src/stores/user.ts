import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const userId = ref('1')
  const userName = ref('LOCAL_HR')

  return { userId, userName }
})
