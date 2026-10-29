"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

type ChatSelectionState = {
  activeChatId: string | null;
  busy: boolean;
  select: (chatId: string | null) => void;
  setBusy: (busy: boolean) => void;
};

export const useChatSelection = create<ChatSelectionState>()(
  persist(
    (set) => ({
      activeChatId: null,
      busy: false,
      select: (chatId) => set({ activeChatId: chatId }),
      setBusy: (busy) => set({ busy }),
    }),
    {
      name: "dana.chatSelection",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ activeChatId: state.activeChatId }),
      skipHydration: true,
    },
  ),
);
