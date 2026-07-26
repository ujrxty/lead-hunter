"use client";

import { useState } from "react";
import { Search, X, Plus, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSearchJobs } from "@/lib/hooks";

export function SearchBar() {
  const [keywords, setKeywords] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [searchType, setSearchType] = useState<"AND" | "OR">("AND");

  const searchMutation = useSearchJobs();

  const addKeyword = () => {
    const trimmed = inputValue.trim();
    if (trimmed && !keywords.includes(trimmed)) {
      setKeywords([...keywords, trimmed]);
      setInputValue("");
    }
  };

  const removeKeyword = (keyword: string) => {
    setKeywords(keywords.filter((k) => k !== keyword));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addKeyword();
    }
  };

  const handleSearch = () => {
    if (keywords.length === 0) return;
    searchMutation.mutate({
      keywords,
      search_type: searchType,
    });
  };

  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-foreground">
            Search Upwork Jobs
          </h2>
          <Badge variant="secondary" className="text-xs">
            Company Finder
          </Badge>
        </div>

        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter keyword and press Enter..."
              className="pl-10 h-11 bg-background"
            />
          </div>
          <Button
            variant="outline"
            onClick={addKeyword}
            disabled={!inputValue.trim()}
            className="h-11"
          >
            <Plus className="h-4 w-4" />
          </Button>
          <Select
            value={searchType}
            onValueChange={(v) => setSearchType(v as "AND" | "OR")}
          >
            <SelectTrigger className="w-24 h-11">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="AND">AND</SelectItem>
              <SelectItem value="OR">OR</SelectItem>
            </SelectContent>
          </Select>
          <Button
            onClick={handleSearch}
            disabled={keywords.length === 0 || searchMutation.isPending}
            className="h-11 px-6 bg-primary hover:bg-primary/90"
          >
            {searchMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Searching...
              </>
            ) : (
              <>
                <Search className="h-4 w-4 mr-2" />
                Search
              </>
            )}
          </Button>
        </div>

        {keywords.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {keywords.map((keyword) => (
              <Badge
                key={keyword}
                variant="secondary"
                className="px-3 py-1.5 text-sm bg-primary/10 text-primary hover:bg-primary/20 cursor-default"
              >
                {keyword}
                <button
                  onClick={() => removeKeyword(keyword)}
                  className="ml-2 hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
            <button
              onClick={() => setKeywords([])}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Clear all
            </button>
          </div>
        )}

        {searchMutation.isSuccess && (
          <div className="flex items-center gap-2 text-sm">
            <Badge variant="outline" className="bg-green-500/10 text-green-600 border-green-500/20">
              Found {searchMutation.data.total_found} jobs
            </Badge>
            <Badge variant="outline" className="bg-blue-500/10 text-blue-600 border-blue-500/20">
              {searchMutation.data.with_company_mention} with company mentions
            </Badge>
          </div>
        )}

        {searchMutation.isError && (
          <p className="text-sm text-destructive">
            Search failed. Make sure the backend is running.
          </p>
        )}
      </div>
    </div>
  );
}
