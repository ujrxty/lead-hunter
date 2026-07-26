import { create } from "zustand";

interface FilterState {
  onlyCompanyMentions: boolean;
  searchTerm: string;
  bookmarkedOnly: boolean;
  minConfidence: number;
  page: number;
  perPage: number;
}

interface AppState extends FilterState {
  setOnlyCompanyMentions: (value: boolean) => void;
  setSearchTerm: (value: string) => void;
  setBookmarkedOnly: (value: boolean) => void;
  setMinConfidence: (value: number) => void;
  setPage: (page: number) => void;
  setPerPage: (perPage: number) => void;
  resetFilters: () => void;
}

const initialFilters: FilterState = {
  onlyCompanyMentions: false,
  searchTerm: "",
  bookmarkedOnly: false,
  minConfidence: 0,
  page: 1,
  perPage: 20,
};

export const useAppStore = create<AppState>((set) => ({
  ...initialFilters,
  setOnlyCompanyMentions: (value) =>
    set({ onlyCompanyMentions: value, page: 1 }),
  setSearchTerm: (value) => set({ searchTerm: value, page: 1 }),
  setBookmarkedOnly: (value) => set({ bookmarkedOnly: value, page: 1 }),
  setMinConfidence: (value) => set({ minConfidence: value, page: 1 }),
  setPage: (page) => set({ page }),
  setPerPage: (perPage) => set({ perPage, page: 1 }),
  resetFilters: () => set(initialFilters),
}));
