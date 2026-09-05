/* Original ARPANET Redux utility, compiled by the guest's V6 C compiler.
 * Run under init's single-user shell. Keep that shell and init waiting while
 * stopping other user processes, flushing their writes, and awaiting WRU.
 * This does not preserve unsaved application memory.
 */
main(argc, argv)
int argc;
char **argv;
{
    register int pid;
    register int me;
    int pass, n, parent;

    if (argc != 3 || getuid() != 0)
        exit(1);
    me = getpid();
    parent = atoi(argv[2]);
    if (parent < 2 || parent == me)
        exit(1);
    if (unlink(argv[0]) < 0)
        exit(1);
    for (pass = 0; pass < 2; pass++) {
        pid = 2;
        for (;;) {
            if (pid != me && pid != parent)
                kill(pid, 9);
            if (pid == 32767)
                break;
            pid++;
        }
    }
    sync();
    sleep(3);
    sync();
    sleep(3);
    for (n = 0; argv[1][n]; n++);
    write(1, "\n", 1);
    write(1, argv[1], n);
    write(1, "\n", 1);
    for (;;)
        sleep(60);
}
