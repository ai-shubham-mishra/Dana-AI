"use client";

import { create } from "zustand";

type ChatSelectionState = {
  activeChatId: string | null;
  busy: boolean;
  select: (chatId: string | null) => void;
  setBusy: (busy: boolean) => void;
};

export const useChatSelection = create<ChatSelectionState>((set) => ({
  activeChatId: null,
  busy: false,
  select: (chatId) => set({ activeChatId: chatId }),
  setBusy: (busy) => set({ busy }),
}));
