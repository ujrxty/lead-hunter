"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { jobsApi } from "./api";
import type { SearchRequest } from "./types";
import { useAppStore } from "./store";

export function useJobs() {
  const {
    page,
    perPage,
    onlyCompanyMentions,
    searchTerm,
    bookmarkedOnly,
    minConfidence,
  } = useAppStore();

  return useQuery({
    queryKey: [
      "jobs",
      page,
      perPage,
      onlyCompanyMentions,
      searchTerm,
      bookmarkedOnly,
      minConfidence,
    ],
    queryFn: () =>
      jobsApi.getJobs({
        page,
        per_page: perPage,
        only_company_mentions: onlyCompanyMentions,
        search: searchTerm || undefined,
        bookmarked: bookmarkedOnly || undefined,
        min_confidence: minConfidence,
      }),
  });
}

export function useJob(id: number) {
  return useQuery({
    queryKey: ["job", id],
    queryFn: () => jobsApi.getJob(id),
    enabled: !!id,
  });
}

export function useUpdateJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      update,
    }: {
      id: number;
      update: Partial<{
        is_bookmarked: boolean;
        is_hidden: boolean;
        notes: string;
      }>;
    }) => jobsApi.updateJob(id, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useSearchJobs() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: SearchRequest) => jobsApi.searchJobs(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["searchHistory"] });
    },
  });
}

export function useSearchHistory() {
  return useQuery({
    queryKey: ["searchHistory"],
    queryFn: jobsApi.getSearchHistory,
  });
}

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: jobsApi.getStats,
  });
}
