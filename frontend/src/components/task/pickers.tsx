"use client";

import * as React from "react";
import { CalendarIcon, Check, Flag, Tag as TagIcon, UserPlus, X } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  formatDueDate,
  initials,
  isOverdue,
  PRIORITIES,
  PRIORITY_META,
  STATUS_TYPE_COLOR,
} from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Member, Priority, Status, Tag, UserSummary } from "@/types/api";

// ---------------------------------------------------------------------------
// Status
// ---------------------------------------------------------------------------

export function StatusDot({ status, className }: { status?: Status; className?: string }) {
  const color = status?.color || (status ? STATUS_TYPE_COLOR[status.type] : "#87909E");
  return (
    <span
      className={cn("inline-block size-2.5 shrink-0 rounded-full", className)}
      style={{ backgroundColor: color }}
      aria-hidden
    />
  );
}

export function StatusPicker({
  value,
  statuses,
  onChange,
  disabled,
  trigger,
}: {
  value: string;
  statuses: Status[];
  onChange: (statusId: string) => void;
  disabled?: boolean;
  trigger?: React.ReactElement;
}) {
  const [open, setOpen] = React.useState(false);
  const current = statuses.find((s) => s.id === value);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        disabled={disabled}
        render={
          trigger ?? (
            <Button variant="ghost" size="sm" className="h-7 gap-1.5 px-2 font-normal" />
          )
        }
      >
        {trigger ? null : (
          <>
            <StatusDot status={current} />
            <span className="truncate text-xs">{current?.name ?? "Status"}</span>
          </>
        )}
      </PopoverTrigger>
      <PopoverContent className="w-52 p-0" align="start">
        <Command>
          <CommandInput placeholder="Change status…" />
          <CommandList>
            <CommandEmpty>No status found.</CommandEmpty>
            <CommandGroup>
              {statuses.map((status) => (
                <CommandItem
                  key={status.id}
                  value={status.name}
                  onSelect={() => {
                    setOpen(false);
                    if (status.id !== value) onChange(status.id);
                  }}
                >
                  <StatusDot status={status} />
                  {status.name}
                  {status.id === value ? <Check className="ml-auto size-4" /> : null}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

// ---------------------------------------------------------------------------
// Priority
// ---------------------------------------------------------------------------

export function PriorityFlag({ priority, className }: { priority: Priority; className?: string }) {
  return (
    <Flag
      className={cn(
        "size-3.5",
        PRIORITY_META[priority].className,
        priority !== "none" && "fill-current",
        className,
      )}
      aria-label={`Priority: ${PRIORITY_META[priority].label}`}
    />
  );
}

export function PriorityPicker({
  value,
  onChange,
  disabled,
  showLabel = false,
}: {
  value: Priority;
  onChange: (p: Priority) => void;
  disabled?: boolean;
  showLabel?: boolean;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={disabled}
        render={
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1.5 px-2 font-normal"
            aria-label="Set priority"
          />
        }
      >
        <PriorityFlag priority={value} />
        {showLabel ? <span className="text-xs">{PRIORITY_META[value].label}</span> : null}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-40">
        {PRIORITIES.map((p) => (
          <DropdownMenuItem key={p} onClick={() => onChange(p)}>
            <PriorityFlag priority={p} />
            {PRIORITY_META[p].label}
            {p === value ? <Check className="ml-auto size-4" /> : null}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// ---------------------------------------------------------------------------
// Assignees
// ---------------------------------------------------------------------------

export function AvatarStack({ users, max = 3 }: { users: UserSummary[]; max?: number }) {
  const shown = users.slice(0, max);
  const extra = users.length - shown.length;
  if (users.length === 0) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  return (
    <span className="flex items-center -space-x-1.5">
      {shown.map((u) => (
        <Avatar key={u.id} className="size-6 ring-2 ring-background">
          {u.avatar ? <AvatarImage src={u.avatar} alt="" /> : null}
          <AvatarFallback
            className="text-[10px] font-semibold text-primary-foreground"
            style={{ backgroundColor: u.avatar_color || "#7B68EE" }}
          >
            {initials(u.full_name, u.email)}
          </AvatarFallback>
        </Avatar>
      ))}
      {extra > 0 ? (
        <span className="flex size-6 items-center justify-center rounded-full bg-muted text-[10px] text-muted-foreground ring-2 ring-background">
          +{extra}
        </span>
      ) : null}
    </span>
  );
}

export function AssigneePicker({
  value,
  members,
  onChange,
  disabled,
  children,
}: {
  value: UserSummary[];
  members: Member[];
  onChange: (ids: string[]) => void;
  disabled?: boolean;
  children?: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(false);
  const selected = new Set(value.map((u) => u.id));

  const toggle = (userId: string) => {
    const next = new Set(selected);
    if (next.has(userId)) next.delete(userId);
    else next.add(userId);
    onChange([...next]);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        disabled={disabled}
        render={
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1 px-1.5 font-normal"
            aria-label="Assignees"
          />
        }
      >
        {children ?? (
          <>
            <AvatarStack users={value} />
            {value.length === 0 ? <UserPlus className="size-3.5 text-muted-foreground" /> : null}
          </>
        )}
      </PopoverTrigger>
      <PopoverContent className="w-60 p-0" align="start">
        <Command>
          <CommandInput placeholder="Assign people…" />
          <CommandList>
            <CommandEmpty>No members found.</CommandEmpty>
            <CommandGroup>
              {members.map((member) => (
                <CommandItem
                  key={member.id}
                  value={`${member.user.full_name} ${member.user.email}`}
                  onSelect={() => toggle(member.user.id)}
                >
                  <Avatar className="size-5">
                    {member.user.avatar ? <AvatarImage src={member.user.avatar} alt="" /> : null}
                    <AvatarFallback
                      className="text-[9px] font-semibold text-primary-foreground"
                      style={{ backgroundColor: member.user.avatar_color || "#7B68EE" }}
                    >
                      {initials(member.user.full_name, member.user.email)}
                    </AvatarFallback>
                  </Avatar>
                  <span className="truncate">
                    {member.user.full_name || member.user.email}
                  </span>
                  {selected.has(member.user.id) ? (
                    <Check className="ml-auto size-4" />
                  ) : null}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

// ---------------------------------------------------------------------------
// Due date
// ---------------------------------------------------------------------------

export function DueDatePicker({
  value,
  onChange,
  disabled,
  overdue,
}: {
  value: string | null;
  onChange: (iso: string | null) => void;
  disabled?: boolean;
  overdue?: boolean;
}) {
  const [open, setOpen] = React.useState(false);
  const date = value ? new Date(value) : undefined;
  const isLate = overdue ?? isOverdue(value);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        disabled={disabled}
        render={
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              "h-7 gap-1.5 px-2 text-xs font-normal",
              isLate ? "text-danger" : "text-muted-foreground",
            )}
            aria-label="Due date"
          />
        }
      >
        <CalendarIcon className="size-3.5" />
        {value ? formatDueDate(value) : "—"}
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={date}
          onSelect={(d) => {
            setOpen(false);
            if (!d) {
              onChange(null);
              return;
            }
            // End of the selected day, UTC-serialised with a trailing Z.
            const end = new Date(d);
            end.setHours(23, 59, 59, 0);
            onChange(end.toISOString().replace(/\.\d{3}Z$/, "Z"));
          }}
        />
        {value ? (
          <div className="border-t p-2">
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-start text-muted-foreground"
              onClick={() => {
                setOpen(false);
                onChange(null);
              }}
            >
              <X className="size-3.5" /> Clear due date
            </Button>
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}

// ---------------------------------------------------------------------------
// Tags
// ---------------------------------------------------------------------------

export function TagChips({
  value,
  max = 2,
}: {
  value: { id: string; name: string; color: string }[];
  max?: number;
}) {
  if (value.length === 0) return <span className="text-xs text-muted-foreground">—</span>;
  const shown = value.slice(0, max);
  const extra = value.length - shown.length;
  return (
    <span className="flex items-center gap-1">
      {shown.map((tag) => (
        <Badge
          key={tag.id}
          variant="secondary"
          className="h-5 gap-1 px-1.5 text-[10px] font-medium"
        >
          <span
            className="size-1.5 rounded-full"
            style={{ backgroundColor: tag.color || "#FD71AF" }}
          />
          {tag.name}
        </Badge>
      ))}
      {extra > 0 ? <span className="text-[10px] text-muted-foreground">+{extra}</span> : null}
    </span>
  );
}

export function TagPicker({
  value,
  tags,
  onChange,
  disabled,
  children,
}: {
  value: { id: string; name: string; color: string }[];
  tags: Tag[];
  onChange: (ids: string[]) => void;
  disabled?: boolean;
  children?: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(false);
  const selected = new Set(value.map((t) => t.id));

  const toggle = (tagId: string) => {
    const next = new Set(selected);
    if (next.has(tagId)) next.delete(tagId);
    else next.add(tagId);
    onChange([...next]);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        disabled={disabled}
        render={
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1 px-1.5 font-normal"
            aria-label="Tags"
          />
        }
      >
        {children ?? (
          <>
            <TagChips value={value} />
            {value.length === 0 ? <TagIcon className="size-3.5 text-muted-foreground" /> : null}
          </>
        )}
      </PopoverTrigger>
      <PopoverContent className="w-56 p-0" align="start">
        <Command>
          <CommandInput placeholder="Add tags…" />
          <CommandList>
            <CommandEmpty>No tags in this workspace.</CommandEmpty>
            <CommandGroup>
              {tags.map((tag) => (
                <CommandItem key={tag.id} value={tag.name} onSelect={() => toggle(tag.id)}>
                  <span
                    className="size-2 rounded-full"
                    style={{ backgroundColor: tag.color || "#FD71AF" }}
                  />
                  {tag.name}
                  {selected.has(tag.id) ? <Check className="ml-auto size-4" /> : null}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
