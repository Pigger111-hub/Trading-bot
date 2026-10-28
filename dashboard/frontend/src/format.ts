export const number = (value: number | null | undefined, digits = 2): string => value == null || !Number.isFinite(value) ? '—' : value.toLocaleString('en-US', {minimumFractionDigits: digits, maximumFractionDigits: digits});
export const percent = (value: number | null | undefined): string => value == null || !Number.isFinite(value) ? '—' : `${value > 0 ? '+' : ''}${number(value)}%`;
export const date = (value: string | null | undefined): string => value ? value.replace('T',' ').replace('+00:00','').replace('Z','') + ' UTC' : '—';
