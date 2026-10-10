// The notes from PROCinfo in the original, adapted for clicking.

import { LANGUAGE } from "../shared/strings";

const EN = [
  "You go out for a walk on a warm, sunny day. You become tired and you fall asleep on a grassy bank. When you wake up you are in a magic land where there are treasures to be found.",
  "To move around, use the compass or the arrow keys (or N, S, E and W). But the task of exploring is not easy. There are many hazards on the way!",
  "As you explore you will find objects which you will need to use to help you. If you carry the objects back to the grassy bank and drop them there then your score will increase.",
  "Click an object to take it. Click it in your hands (or press 1 to 5) to use it if you are in danger. Drop it with the button underneath, or drag it back into the scene.",
  "However, you can only carry with you a maximum of 5 objects at any one time.",
];

const DA = [
  "Du går en tur en varm, solrig dag. Du bliver træt og falder i søvn på en græsklædt skrænt. Da du vågner, er du i et magisk land, hvor der er skatte at finde.",
  "Du kommer rundt med retningsknapperne eller piletasterne (eller N, S, Ø og V). Men det er ikke let at gå på opdagelse. Der er mange farer på vejen!",
  "Mens du udforsker, finder du genstande, som du får brug for. Hvis du bærer genstandene tilbage til den græsklædte skrænt og lægger dem der, stiger dine point.",
  "Klik på en genstand for at tage den. Klik på den i dine hænder (eller tryk 1 til 5) for at bruge den, hvis du er i fare. Læg den fra dig med knappen nedenunder, eller træk den tilbage ind i billedet.",
  "Du kan dog højst bære 5 genstande ad gangen.",
];

export const NOTES = LANGUAGE === "da" ? DA : EN;
