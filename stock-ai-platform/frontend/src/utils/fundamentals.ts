import { formatInr } from "./quote.ts";
import type { MetricUnit } from "../components/fundamentals/definitions.ts";

export function formatMetricValue(unit: MetricUnit, value: string | null): string | null {
  if (value === null || value.trim() === "") {
    return null;
  }
  if (unit === "money" || unit === "per_share") {
    return formatInr(value);
  }
  if (!/^-?\d+(\.\d+)?$/.test(value)) {
    return null;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  if (unit === "percent") {
    return `${parsed.toFixed(2)}%`;
  }
  return parsed.toFixed(2);
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function formatReportDay(isoDate: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  if (match === null) {
    return null;
  }
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) {
    return null;
  }
  return `${day} ${MONTHS[month - 1]} ${match[1]}`;
}

export function formatSnapshotDay(isoDateTime: string): string | null {
  const parsed = new Date(isoDateTime);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  const parts = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "2-digit",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  }).formatToParts(parsed);
  const day = parts.find((part) => part.type === "day")?.value;
  const month = parts.find((part) => part.type === "month")?.value;
  const year = parts.find((part) => part.type === "year")?.value;
  if (day === undefined || month === undefined || year === undefined) {
    return null;
  }
  const monthIndex = Number(month) - 1;
  if (monthIndex < 0 || monthIndex > 11) {
    return null;
  }
  return `${Number(day)} ${MONTHS[monthIndex]} ${year}`;
}
