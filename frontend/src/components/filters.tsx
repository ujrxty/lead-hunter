"use client";

import { Filter, Building2, Bookmark, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useAppStore } from "@/lib/store";

export function Filters() {
  const {
    onlyCompanyMentions,
    setOnlyCompanyMentions,
    searchTerm,
    setSearchTerm,
    bookmarkedOnly,
    setBookmarkedOnly,
    resetFilters,
  } = useAppStore();

  const hasActiveFilters = onlyCompanyMentions || bookmarkedOnly || searchTerm;

  return (
    <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium text-foreground">Filters</span>
        </div>
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={resetFilters}
            className="h-8 text-xs"
          >
            <RotateCcw className="h-3 w-3 mr-1" />
            Reset
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Input
          placeholder="Search jobs..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-64 h-9 bg-background"
        />

        <Separator orientation="vertical" className="h-8" />

        <Button
          variant={onlyCompanyMentions ? "default" : "outline"}
          size="sm"
          onClick={() => setOnlyCompanyMentions(!onlyCompanyMentions)}
          className="h-9"
        >
          <Building2 className="h-4 w-4 mr-2" />
          Company Mentioned
          {onlyCompanyMentions && (
            <Badge
              variant="secondary"
              className="ml-2 h-5 px-1.5 bg-white/20"
            >
              ON
            </Badge>
          )}
        </Button>

        <Button
          variant={bookmarkedOnly ? "default" : "outline"}
          size="sm"
          onClick={() => setBookmarkedOnly(!bookmarkedOnly)}
          className="h-9"
        >
          <Bookmark className="h-4 w-4 mr-2" />
          Bookmarked
          {bookmarkedOnly && (
            <Badge
              variant="secondary"
              className="ml-2 h-5 px-1.5 bg-white/20"
            >
              ON
            </Badge>
          )}
        </Button>
      </div>
    </div>
  );
}
