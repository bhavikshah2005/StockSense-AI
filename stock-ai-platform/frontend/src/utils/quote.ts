const inr = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function amount(value: string): number | null {
  if (!/^-?\d+(\.\d+)?$/.test(value)) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatInr(value: string): string | null {
  const parsed = amount(value);
  if (parsed === null) {
    return null;
  }
  return inr.format(parsed);
}

export function formatSignedInr(value: string): string | null {
  const parsed = amount(value);
  if (parsed === null) {
    return null;
  }
  const formatted = inr.format(Math.abs(parsed));
  if (parsed > 0) {
    return `+${formatted}`;
  }
  if (parsed < 0) {
    return `-${formatted}`;
  }
  return formatted;
}

export function formatSignedPercent(value: string): string | null {
  const parsed = amount(value);
  if (parsed === null) {
    return null;
  }
  const absolute = Math.abs(parsed).toFixed(2);
  if (parsed > 0) {
    return `+${absolute}%`;
  }
  if (parsed < 0) {
    return `-${absolute}%`;
  }
  return `${absolute}%`;
}

export function formatIst(value: string): string | null {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  const formatted = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).format(parsed);
  return `${formatted} IST`;
}

export function formatVolume(value: number): string | null {
  if (!Number.isInteger(value) || value < 0) {
    return null;
  }
  return new Intl.NumberFormat("en-IN").format(value);
}

export function formatCompactVolume(value: number): string | null {
  if (!Number.isInteger(value) || value < 0) {
    return null;
  }
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`;
  }
  return String(value);
}
