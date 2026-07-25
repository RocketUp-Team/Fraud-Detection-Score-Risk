import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../lib/api'
import type { ReviewRequest, TransactionListParams } from '../types/api'

export function useMeta() {
  return useQuery({
    queryKey: ['meta'],
    queryFn: () => api.meta(),
    // Model version không đổi trong 1 buổi demo.
    staleTime: 5 * 60 * 1000,
  })
}

export function useStats() {
  return useQuery({ queryKey: ['stats'], queryFn: () => api.stats() })
}

export function useTransactions(params: TransactionListParams) {
  return useQuery({
    queryKey: ['transactions', params],
    queryFn: () => api.listTransactions(params),
    // Giữ trang cũ trong lúc tải trang mới -> không nhảy layout khi phân trang.
    placeholderData: (prev) => prev,
  })
}

export function useTransaction(id: number | null) {
  return useQuery({
    queryKey: ['transaction', id],
    queryFn: () => api.getTransaction(id as number),
    enabled: id !== null,
  })
}

export function useSubmitReview(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ReviewRequest) => api.submitReview(id, payload),
    onSuccess: (detail) => {
      // Backend trả detail đã cập nhật -> ghi thẳng vào cache, không cần refetch.
      queryClient.setQueryData(['transaction', id], detail)
      // Danh sách có cột review_status, và KPI có "chờ rà soát" -> làm mới cả hai.
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })
}
