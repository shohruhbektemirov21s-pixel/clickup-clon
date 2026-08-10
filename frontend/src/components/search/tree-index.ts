/**
 * Qidiruv natijalari uchun kontekst yo'lini ("Product › Q3 Roadmap › Sprint 24")
 * tuzuvchi indeks.
 *
 * `GET workspaces/{id}/search/` faqat yalang'och obyektlarni qaytaradi:
 * vazifada `list_id`, ro'yxatda `space_id`/`folder_id` bor, lekin nomlar yo'q.
 * Nomlar allaqachon keshda turgan `workspaces/{id}/tree/` javobida bor, shuning
 * uchun yo'l butunlay klient tomonda yig'iladi — qo'shimcha so'rov yo'q.
 */

import type { WorkspaceTree } from "@/types/api";

export const PATH_SEPARATOR = " › ";

export interface IndexedList {
  id: string;
  name: string;
  /** Ota-onalar nomlari, eng yuqorisidan boshlab (ro'yxatning o'zisiz). */
  path: string[];
}

export interface IndexedFolder {
  id: string;
  name: string;
  path: string[];
  /** Jildning birinchi ro'yxati — jildning o'z sahifasi yo'q, shunga o'tamiz. */
  firstListId: string | null;
}

export interface IndexedSpace {
  id: string;
  name: string;
  color: string;
  firstListId: string | null;
}

export interface TreeIndex {
  lists: Map<string, IndexedList>;
  folders: Map<string, IndexedFolder>;
  spaces: Map<string, IndexedSpace>;
}

export const EMPTY_TREE_INDEX: TreeIndex = {
  lists: new Map(),
  folders: new Map(),
  spaces: new Map(),
};

export function buildTreeIndex(tree: WorkspaceTree | undefined): TreeIndex {
  if (!tree) return EMPTY_TREE_INDEX;

  const index: TreeIndex = { lists: new Map(), folders: new Map(), spaces: new Map() };

  for (const space of tree.spaces) {
    // Bo'limning "birinchi ro'yxati" — avval jildsiz ro'yxatlar, keyin
    // jildlardagilar; daraxt allaqachon `position` bo'yicha saralangan keladi.
    let spaceFirstList: string | null = space.lists[0]?.id ?? null;

    for (const list of space.lists) {
      index.lists.set(list.id, { id: list.id, name: list.name, path: [space.name] });
    }

    for (const folder of space.folders) {
      const folderFirstList = folder.lists[0]?.id ?? null;
      if (!spaceFirstList) spaceFirstList = folderFirstList;
      index.folders.set(folder.id, {
        id: folder.id,
        name: folder.name,
        path: [space.name],
        firstListId: folderFirstList,
      });
      for (const list of folder.lists) {
        index.lists.set(list.id, {
          id: list.id,
          name: list.name,
          path: [space.name, folder.name],
        });
      }
    }

    index.spaces.set(space.id, {
      id: space.id,
      name: space.name,
      color: space.color,
      firstListId: spaceFirstList,
    });
  }

  return index;
}

/** `["Product", "Q3 Roadmap"]` → `"Product › Q3 Roadmap"`. Bo'sh bo'lsa `""`. */
export function joinPath(parts: Array<string | undefined | null>): string {
  return parts.filter((part): part is string => !!part && part.length > 0).join(PATH_SEPARATOR);
}

/** Vazifa uchun to'liq yo'l: bo'lim › jild › ro'yxat. */
export function taskPath(index: TreeIndex, listId: string): string {
  const list = index.lists.get(listId);
  if (!list) return "";
  return joinPath([...list.path, list.name]);
}

/** Vazifa ochiladigan manzil — ro'yxat sahifasi + `?task=` chuqur havolasi. */
export function taskHref(workspaceId: string, listId: string, taskId: string): string {
  return `/w/${workspaceId}/l/${listId}?task=${taskId}`;
}

export function listHref(workspaceId: string, listId: string): string {
  return `/w/${workspaceId}/l/${listId}`;
}

/**
 * Bo'lim/jildning o'z route'i yo'q (`app/(app)/w/[workspaceId]/…` da faqat
 * `l/[listId]` bor), shuning uchun ularni ochish ichidagi birinchi ro'yxatga
 * o'tishni bildiradi. Ro'yxat topilmasa `null` — element bosilmaydigan bo'ladi.
 */
export function containerHref(workspaceId: string, firstListId: string | null): string | null {
  return firstListId ? listHref(workspaceId, firstListId) : null;
}

export function memberHref(workspaceId: string, userId: string): string {
  return `/w/${workspaceId}/u/${userId}`;
}
