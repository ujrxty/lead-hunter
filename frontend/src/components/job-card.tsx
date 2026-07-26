"use client";

import {
  Building2,
  MapPin,
  DollarSign,
  Star,
  Bookmark,
  ExternalLink,
  Clock,
  Eye,
  EyeOff,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useUpdateJob } from "@/lib/hooks";
import type { Job } from "@/lib/types";

interface JobCardProps {
  job: Job;
}

export function JobCard({ job }: JobCardProps) {
  const updateMutation = useUpdateJob();

  const toggleBookmark = () => {
    updateMutation.mutate({
      id: job.id,
      update: { is_bookmarked: !job.is_bookmarked },
    });
  };

  const toggleHide = () => {
    updateMutation.mutate({
      id: job.id,
      update: { is_hidden: !job.is_hidden },
    });
  };

  const confidenceColor =
    job.company_confidence >= 0.9
      ? "text-emerald-500 bg-emerald-500/10"
      : job.company_confidence >= 0.7
        ? "text-blue-500 bg-blue-500/10"
        : "text-amber-500 bg-amber-500/10";

  return (
    <Card
      className={`border-border hover:border-primary/30 transition-all duration-200 ${
        job.has_company_mention
          ? "ring-1 ring-emerald-500/20 bg-emerald-500/[0.02]"
          : ""
      }`}
    >
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              {job.has_company_mention && (
                <Badge
                  variant="secondary"
                  className={`text-xs font-medium ${confidenceColor}`}
                >
                  <Building2 className="h-3 w-3 mr-1" />
                  {job.detected_company_name}
                </Badge>
              )}
              {job.is_bookmarked && (
                <Badge
                  variant="secondary"
                  className="text-xs bg-amber-500/10 text-amber-500"
                >
                  <Bookmark className="h-3 w-3 mr-1 fill-current" />
                  Saved
                </Badge>
              )}
            </div>

            <h3 className="font-semibold text-foreground mb-2 line-clamp-2 hover:text-primary transition-colors">
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline"
              >
                {job.title}
              </a>
            </h3>

            <p className="text-sm text-muted-foreground line-clamp-3 mb-4">
              {job.description}
            </p>

            {job.has_company_mention && job.company_context && (
              <div className="mb-4 p-3 rounded-lg bg-primary/5 border border-primary/10">
                <p className="text-xs font-medium text-primary mb-1">
                  Company Context
                </p>
                <p className="text-sm text-muted-foreground italic">
                  &quot;...{job.company_context}...&quot;
                </p>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
              {job.client_country && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" />
                  {job.client_country}
                </span>
              )}
              {job.budget_min && (
                <span className="flex items-center gap-1">
                  <DollarSign className="h-3.5 w-3.5" />
                  {job.budget_type === "hourly"
                    ? `$${job.budget_min}${job.budget_max ? `-${job.budget_max}` : ""}/hr`
                    : `$${job.budget_min.toLocaleString()}`}
                </span>
              )}
              {job.client_rating && (
                <span className="flex items-center gap-1">
                  <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
                  {job.client_rating.toFixed(1)}
                </span>
              )}
              {job.posted_at && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" />
                  {new Date(job.posted_at).toLocaleDateString()}
                </span>
              )}
            </div>

            {job.search_keywords && job.search_keywords.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-3">
                {job.search_keywords.map((kw) => (
                  <Badge
                    key={kw}
                    variant="outline"
                    className="text-xs px-2 py-0.5"
                  >
                    {kw}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleBookmark}
              className={`h-9 w-9 ${
                job.is_bookmarked
                  ? "text-amber-500 hover:text-amber-600"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Bookmark
                className={`h-4 w-4 ${job.is_bookmarked ? "fill-current" : ""}`}
              />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleHide}
              className="h-9 w-9 text-muted-foreground hover:text-foreground"
            >
              {job.is_hidden ? (
                <Eye className="h-4 w-4" />
              ) : (
                <EyeOff className="h-4 w-4" />
              )}
            </Button>
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center h-9 w-9 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
