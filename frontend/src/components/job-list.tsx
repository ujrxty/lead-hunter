"use client";

import { ChevronLeft, ChevronRight, Inbox } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { JobCard } from "./job-card";
import { useJobs } from "@/lib/hooks";
import { useAppStore } from "@/lib/store";

export function JobList() {
  const { page, setPage, perPage } = useAppStore();
  const { data, isLoading, isError } = useJobs();

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="bg-card border border-border rounded-xl p-5">
            <Skeleton className="h-5 w-32 mb-3" />
            <Skeleton className="h-6 w-3/4 mb-2" />
            <Skeleton className="h-4 w-full mb-1" />
            <Skeleton className="h-4 w-2/3 mb-4" />
            <div className="flex gap-4">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-16" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="bg-card border border-border rounded-xl p-12 text-center">
        <p className="text-destructive mb-2">Failed to load jobs</p>
        <p className="text-sm text-muted-foreground">
          Make sure the backend server is running on port 8500
        </p>
      </div>
    );
  }

  if (!data || data.jobs.length === 0) {
    return (
      <div className="bg-card border border-border rounded-xl p-12 text-center">
        <Inbox className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
        <p className="text-lg font-medium text-foreground mb-2">No jobs found</p>
        <p className="text-sm text-muted-foreground">
          Try searching with different keywords or adjust your filters
        </p>
      </div>
    );
  }

  const totalPages = Math.ceil(data.total / perPage);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Showing {(page - 1) * perPage + 1}-
          {Math.min(page * perPage, data.total)} of {data.total} jobs
          {data.has_company_mention_count > 0 && (
            <span className="ml-2 text-emerald-500">
              ({data.has_company_mention_count} with company mentions)
            </span>
          )}
        </p>
      </div>

      <div className="space-y-3">
        {data.jobs.map((job) => (
          <JobCard key={job.id} job={job} />
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page - 1)}
            disabled={page <= 1}
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Previous
          </Button>
          <div className="flex items-center gap-1 px-4">
            {[...Array(Math.min(5, totalPages))].map((_, i) => {
              const pageNum =
                page <= 3
                  ? i + 1
                  : page >= totalPages - 2
                    ? totalPages - 4 + i
                    : page - 2 + i;
              if (pageNum < 1 || pageNum > totalPages) return null;
              return (
                <Button
                  key={pageNum}
                  variant={pageNum === page ? "default" : "ghost"}
                  size="sm"
                  onClick={() => setPage(pageNum)}
                  className="h-8 w-8 p-0"
                >
                  {pageNum}
                </Button>
              );
            })}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page + 1)}
            disabled={page >= totalPages}
          >
            Next
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      )}
    </div>
  );
}
