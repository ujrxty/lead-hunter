"use client";

import { Briefcase, Building2, Bookmark, TrendingUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useStats } from "@/lib/hooks";

export function StatsCards() {
  const { data: stats, isLoading } = useStats();

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="border-border">
            <CardContent className="p-6">
              <Skeleton className="h-4 w-24 mb-2" />
              <Skeleton className="h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const cards = [
    {
      label: "Total Jobs",
      value: stats?.total_jobs ?? 0,
      icon: Briefcase,
      color: "text-blue-500",
      bg: "bg-blue-500/10",
    },
    {
      label: "With Company",
      value: stats?.jobs_with_company ?? 0,
      icon: Building2,
      color: "text-emerald-500",
      bg: "bg-emerald-500/10",
    },
    {
      label: "Bookmarked",
      value: stats?.bookmarked_jobs ?? 0,
      icon: Bookmark,
      color: "text-amber-500",
      bg: "bg-amber-500/10",
    },
    {
      label: "Detection Rate",
      value:
        stats && stats.total_jobs > 0
          ? `${Math.round((stats.jobs_with_company / stats.total_jobs) * 100)}%`
          : "0%",
      icon: TrendingUp,
      color: "text-purple-500",
      bg: "bg-purple-500/10",
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      {cards.map((card) => (
        <Card
          key={card.label}
          className="border-border hover:border-primary/50 transition-colors"
        >
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">
                  {card.label}
                </p>
                <p className="text-2xl font-bold text-foreground">
                  {card.value}
                </p>
              </div>
              <div className={`p-3 rounded-xl ${card.bg}`}>
                <card.icon className={`h-5 w-5 ${card.color}`} />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
