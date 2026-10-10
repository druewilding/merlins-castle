// The in-game notes, from PROCinfo in MERLIN2. The typed commands are
// adapted for clicking. "" is a blank row.

import { LANGUAGE } from "../shared/strings";

const EN: string[][] = [
  [
    "{blue}Merlin's Castle",
    "",
    "You go out for a walk on a warm, sunny day. You become tired and you fall asleep on a grassy bank. When you wake up you are in a magic land where there are treasures to be found.",
    "",
    "To move around, click the{yellow}arrows{white}or press{yellow}N, S, E, W{white}or the{yellow}arrow keys.",
    "",
    "But the task of exploring is not easy. There are many hazards on the way!",
  ],
  [
    "As you explore you will find objects which you will need to use to help you. If you carry the objects back to the grassy bank and drop them there then your score will increase.",
    "",
    "Click an object to{yellow}take{white}it.{yellow}Use{white}it if you are in danger, then{yellow}drop{white}it on the grassy bank.",
    "",
    "However, you can only carry with you a maximum of 5 objects at any one time.",
  ],
];

const DA: string[][] = [
  [
    "{blue}Merlin's Castle",
    "",
    "Du går en tur en varm, solrig dag. Du bliver træt og falder i søvn på en græsklædt skrænt. Når du vågner, er du i et magisk land, hvor der er skatte at finde.",
    "",
    "Du kommer rundt ved at klikke på{yellow}pilene{white}eller trykke på{yellow}N, S, Ø, V{white}eller{yellow}piletasterne.",
    "",
    "Men det er ikke let at gå på opdagelse. Der er mange farer på vejen!",
  ],
  [
    "Mens du udforsker, finder du genstande, som du får brug for. Hvis du bærer genstandene tilbage til den græsklædte skrænt og lægger dem der, stiger dine point.",
    "",
    "Klik på en genstand for at{yellow}tage{white}den.{yellow}Brug{white}den, hvis du er i fare, og{yellow}læg{white}den så på den græsklædte skrænt.",
    "",
    "Du kan dog højst bære 5 genstande ad gangen.",
  ],
];

export const NOTES = LANGUAGE === "da" ? DA : EN;
