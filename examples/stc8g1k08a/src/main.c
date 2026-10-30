#include "stc8g1k08a.h"
#include "fwid_generated.h"

/*
 * STC8G1K08A FWID example.
 *
 * Clock: 24 MHz internal IRC (set in STC-ISP).
 * UART1: P3.0 = RXD, P3.1 = TXD, 115200 8N1.
 *
 * The STC8G1K08A-8PIN has no Timer2, so UART1 uses Timer1
 * mode 0 (16-bit auto-reload) as its baud clock.
 * T1x12 = 1, S1ST2 = 0.
 *
 * On reset the firmware prints one line:
 *   FWID:STC8G1K08A01C6
 *
 * The string is stored in code memory and is part of the image.
 */

#define FOSC 24000000UL
#define UART_BAUD 115200UL

/* Timer1 1T reload: 65536 - FOSC / (4 * BAUD). */
#define T1_RELOAD (65536UL - (FOSC / 4UL / UART_BAUD))

/* Keep the canonical FWID string in code memory. */
const char code fwid_string[] = FWID_STRING;

void Uart1_Init(void)
{
    SCON = 0x40;      /* UART1 mode 1, 8-bit, TX only */
    AUXR |= 0x40;     /* T1x12 = 1: Timer1 counts at FOSC */
    AUXR &= ~0x01;    /* S1ST2 = 0: UART1 uses Timer1 */
    TMOD &= 0x0F;     /* Timer1 mode 0, 16-bit auto-reload */
    TL1 = (unsigned char)(T1_RELOAD);
    TH1 = (unsigned char)(T1_RELOAD >> 8);
    ET1 = 0;
    TR1 = 1;

    P3M1 &= ~(1U << 1);  /* P3.1 push-pull TXD */
    P3M0 |=  (1U << 1);
}

void Uart1_SendByte(unsigned char dat)
{
    SBUF = dat;
    while (!TI) {
    }
    TI = 0;
}

void Uart1_SendStr(const char *s)
{
    while (*s) {
        Uart1_SendByte(*s++);
    }
}

void main(void)
{
    Uart1_Init();

    Uart1_SendByte('\r');
    Uart1_SendByte('\n');
    Uart1_SendStr(fwid_string);
    Uart1_SendByte('\r');
    Uart1_SendByte('\n');

    for (;;) {
        /* The FWID is printed once per boot. */
    }
}
