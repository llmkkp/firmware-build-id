#ifndef STC8G1K08A_H
#define STC8G1K08A_H

/*
 * Minimal STC8G1K08A SFR definitions for Keil C51.
 *
 * Only the registers used by this example are defined here. Keil's
 * reg51.h provides P3, SCON, SBUF, PCON, TI, and RI.
 *
 * Reference: STC8G series datasheet, SFR map.
 */

#include <reg51.h>

sfr P3M1 = 0xB1;
sfr P3M0 = 0xB2;
sfr AUXR = 0x8E;

#endif
