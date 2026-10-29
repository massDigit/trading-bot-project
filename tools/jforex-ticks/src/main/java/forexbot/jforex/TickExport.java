package forexbot.jforex;

import com.dukascopy.api.IAccount;
import com.dukascopy.api.IBar;
import com.dukascopy.api.IContext;
import com.dukascopy.api.IHistory;
import com.dukascopy.api.IMessage;
import com.dukascopy.api.IStrategy;
import com.dukascopy.api.ITick;
import com.dukascopy.api.Instrument;
import com.dukascopy.api.Period;
import com.dukascopy.api.system.ClientFactory;
import com.dukascopy.api.system.IClient;
import com.dukascopy.api.system.ISystemListener;

import java.io.IOException;
import java.io.OutputStream;
import java.io.PrintStream;
import java.io.Writer;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.DayOfWeek;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

/**
 * Read-only export of EUR/USD ticks through the JForex SDK, DEMO server only.
 *
 * <p>Writes one CSV per UTC day ({@code <out>/EURUSD/<yyyy-mm-dd>.csv}) plus a JSON sidecar.
 * A day is written atomically once its 24 hourly windows are loaded; an existing day file is
 * skipped, so an interrupted run resumes at the first missing day.
 *
 * <p>Window rule (see src/forex_bot/history/jforex.py): to cover [start, end) request
 * [start - 1, end - 1] and keep start <= time < end. Ticks are never de-duplicated by value.
 *
 * <p>Safety: the demo JNLP address is a constant; no PIN (required by live servers) is ever
 * sent; the trading engine of the context is never accessed; credentials are read from the
 * env file given on the command line and are masked in every console output.
 */
public final class TickExport {

    static final String DEMO_JNLP = "https://platform.dukascopy.com/demo/jforex.jnlp";
    static final Instrument INSTRUMENT = Instrument.EURUSD;
    // Development and validation partitions only; the final test (2024-2025) is refused.
    static final LocalDate ALLOWED_FROM = LocalDate.of(2015, 1, 1);
    static final LocalDate ALLOWED_TO = LocalDate.of(2024, 1, 1);
    static final long HOUR_MS = 3_600_000L;
    static final String FORMAT = "jforex-sdk-ticks-csv-v1";
    static final String HEADER = "time_ms,ask,bid,ask_volume,bid_volume";
    static final ZoneId NEW_YORK = ZoneId.of("America/New_York");
    static final int MAX_ATTEMPTS = 5;
    static final long RETRY_BASE_MS = 5_000L; // 5, 10, 20, 40 s
    // Session tokens that appear in SDK log URLs.
    static final java.util.regex.Pattern URL_TOKEN = java.util.regex.Pattern.compile("(check|token|session)=[^&\\s]+");

    private TickExport() {
    }

    public static void main(String[] argv) throws Exception {
        Map<String, String> args = parseArgs(argv);
        Path envFile = Path.of(require(args, "env-file"));
        Path outDir = Path.of(require(args, "out")).resolve(INSTRUMENT.name().replace("/", ""));
        Path cacheDir = Path.of(require(args, "cache"));
        LocalDate from = LocalDate.parse(require(args, "from"));
        LocalDate to = LocalDate.parse(require(args, "to")); // exclusive
        long pauseMs = Long.parseLong(args.getOrDefault("pause-ms", "250"));
        if (!from.isBefore(to) || from.isBefore(ALLOWED_FROM) || to.isAfter(ALLOWED_TO)) {
            fail("période refusée : [" + from + ", " + to + ") doit être non vide et dans ["
                    + ALLOWED_FROM + ", " + ALLOWED_TO + ") (test final 2024-2025 exclu)");
        }

        Map<String, String> env = readEnv(envFile, Set.of("DUKASCOPY_USERNAME", "DUKASCOPY_PASSWORD"));
        String username = env.get("DUKASCOPY_USERNAME");
        String password = env.get("DUKASCOPY_PASSWORD");
        if (username == null || username.isBlank() || password == null || password.isBlank()) {
            fail("DUKASCOPY_USERNAME ou DUKASCOPY_PASSWORD absent du fichier d'environnement");
        }
        // Every console line, including SDK logs and stack traces, goes through the mask.
        System.setOut(new MaskingStream(System.out, List.of(username, password)));
        System.setErr(new MaskingStream(System.err, List.of(username, password)));

        Files.createDirectories(outDir);
        Files.createDirectories(cacheDir);
        List<LocalDate> pending = new ArrayList<>();
        for (LocalDate day = from; day.isBefore(to); day = day.plusDays(1)) {
            if (!Files.exists(dayCsv(outDir, day))) {
                pending.add(day);
            }
        }
        System.out.println("Jours demandés : " + from + " → " + to + " (exclu) ; à télécharger : " + pending.size());
        if (pending.isEmpty()) {
            return;
        }

        IClient client = ClientFactory.getDefaultInstance();
        CompletableFuture<Void> connected = new CompletableFuture<>();
        client.setSystemListener(new ISystemListener() {
            @Override public void onStart(long processId) { }
            @Override public void onStop(long processId) { }
            @Override public void onConnect() { connected.complete(null); }
            @Override public void onDisconnect() { System.out.println("Déconnecté du serveur démo."); }
        });
        client.setCacheDirectory(cacheDir.toFile());
        System.out.println("Connexion au serveur DÉMO JForex…");
        client.connect(DEMO_JNLP, username, password);
        connected.get(60, TimeUnit.SECONDS);
        if (!client.isConnected()) {
            fail("connexion démo non établie");
        }
        client.setSubscribedInstruments(Set.of(INSTRUMENT));

        HistoryOnly strategy = new HistoryOnly();
        long processId = client.startStrategy(strategy);
        int exit = 0;
        try {
            IHistory history = strategy.history.get(60, TimeUnit.SECONDS);
            int incomplete = 0;
            for (LocalDate day : pending) {
                if (!exportDay(history, outDir, cacheDir, day, pauseMs)) {
                    incomplete++;
                }
            }
            if (incomplete > 0) {
                System.err.println(incomplete + " jour(s) incomplet(s) non écrit(s) : voir les fichiers *.incomplete.json");
                exit = 3;
            }
        } catch (Exception e) {
            System.err.println("ÉCHEC : " + e.getClass().getSimpleName() + " : " + e.getMessage());
            exit = 1;
        } finally {
            client.stopStrategy(processId);
            client.disconnect();
        }
        System.exit(exit);
    }

    /**
     * Loads the 24 hourly windows of a UTC day, then writes CSV and sidecar atomically.
     *
     * <p>Observed on 2026-10-28: when the SDK's datafeed answers HTTP 503 for an hour, getTicks
     * returns an EMPTY list without throwing, and the SDK cache keeps a 0-byte file for that hour,
     * which makes every later request return empty too. Before each request of an hour where the
     * market is expected open, a 0-byte cache file of that hour is deleted; an empty hour is
     * retried with a growing pause; if it stays empty the day is NOT written (a
     * {@code <day>.incomplete.json} report is written instead) and a later run retries it.
     *
     * @return true if the day was written
     */
    static boolean exportDay(IHistory history, Path outDir, Path cacheDir, LocalDate day, long pauseMs) throws Exception {
        long dayStart = day.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli();
        List<ITick> kept = new ArrayList<>();
        int[] perHour = new int[24];
        int[] retries = new int[24];
        List<Integer> emptyOpenHours = new ArrayList<>();
        int discarded = 0;
        long started = System.nanoTime();
        for (int hour = 0; hour < 24; hour++) {
            long start = dayStart + hour * HOUR_MS;
            long end = start + HOUR_MS;
            List<ITick> inWindow = new ArrayList<>();
            int windowDiscarded = 0;
            for (int attempt = 1; ; attempt++) {
                inWindow.clear();
                windowDiscarded = 0;
                if (expectedOpen(start)) {
                    dropEmptyCacheFile(cacheDir, start);
                }
                for (ITick tick : history.getTicks(INSTRUMENT, start - 1, end - 1)) {
                    if (start <= tick.getTime() && tick.getTime() < end) {
                        inWindow.add(tick);
                    } else {
                        windowDiscarded++;
                    }
                }
                Thread.sleep(pauseMs);
                if (!inWindow.isEmpty() || !expectedOpen(start) || attempt >= MAX_ATTEMPTS) {
                    break;
                }
                retries[hour]++;
                Thread.sleep(RETRY_BASE_MS << (attempt - 1));
            }
            if (inWindow.isEmpty() && expectedOpen(start)) {
                emptyOpenHours.add(hour);
            }
            kept.addAll(inWindow);
            perHour[hour] = inWindow.size();
            discarded += windowDiscarded;
        }
        if (!emptyOpenHours.isEmpty()) {
            String report = "{\n  \"day\": \"" + day + "\",\n  \"checked_at_utc\": \"" + Instant.now()
                    + "\",\n  \"empty_hours_while_expected_open_utc\": " + emptyOpenHours
                    + ",\n  \"rows_per_hour\": " + java.util.Arrays.toString(perHour) + "\n}\n";
            Files.writeString(outDir.resolve(day + ".incomplete.json"), report, StandardCharsets.UTF_8);
            System.out.println(day + " : INCOMPLET, heures UTC vides alors que le marché est attendu ouvert : "
                    + emptyOpenHours + " ; jour non écrit");
            return false;
        }
        Files.deleteIfExists(outDir.resolve(day + ".incomplete.json"));
        int outOfOrder = 0;
        for (int i = 1; i < kept.size(); i++) {
            if (kept.get(i).getTime() < kept.get(i - 1).getTime()) {
                outOfOrder++;
            }
        }
        long elapsedMs = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started);
        int retryTotal = java.util.Arrays.stream(retries).sum();

        Path csv = dayCsv(outDir, day);
        Path tmp = outDir.resolve(day + ".csv.tmp-" + ProcessHandle.current().pid());
        try (Writer w = Files.newBufferedWriter(tmp, StandardCharsets.UTF_8)) {
            w.write(HEADER + "\n");
            for (ITick t : kept) {
                w.write(t.getTime() + "," + plain(t.getAsk()) + "," + plain(t.getBid()) + ","
                        + plain(t.getAskVolume()) + "," + plain(t.getBidVolume()) + "\n");
            }
        }
        StringBuilder hours = new StringBuilder();
        for (int h = 0; h < 24; h++) {
            hours.append(h == 0 ? "" : ", ").append(perHour[h]);
        }
        String sidecar = "{\n"
                + "  \"format\": \"" + FORMAT + "\",\n"
                + "  \"instrument\": \"EURUSD\",\n"
                + "  \"server\": \"demo\",\n"
                + "  \"period_start_utc\": \"" + Instant.ofEpochMilli(dayStart) + "\",\n"
                + "  \"period_end_utc\": \"" + Instant.ofEpochMilli(dayStart + 24 * HOUR_MS) + "\",\n"
                + "  \"retrieved_at_utc\": \"" + Instant.now() + "\",\n"
                + "  \"window_rule\": \"request [start-1, end-1] ms per UTC hour, keep start <= time < end\",\n"
                + "  \"rows\": " + kept.size() + ",\n"
                + "  \"rows_per_hour\": [" + hours + "],\n"
                + "  \"discarded_outside_window\": " + discarded + ",\n"
                + "  \"out_of_order\": " + outOfOrder + ",\n"
                + "  \"retries_per_hour\": " + java.util.Arrays.toString(retries) + ",\n"
                + "  \"elapsed_ms\": " + elapsedMs + "\n"
                + "}\n";
        Path sidecarTmp = outDir.resolve(day + ".json.tmp-" + ProcessHandle.current().pid());
        Files.writeString(sidecarTmp, sidecar, StandardCharsets.UTF_8);
        Files.move(sidecarTmp, outDir.resolve(day + ".json"), StandardCopyOption.ATOMIC_MOVE,
                StandardCopyOption.REPLACE_EXISTING);
        // The CSV is the completion marker: it is moved last.
        Files.move(tmp, csv, StandardCopyOption.ATOMIC_MOVE);
        System.out.println(day + " : " + kept.size() + " ticks, " + discarded + " hors fenêtre, "
                + outOfOrder + " hors ordre, " + retryTotal + " nouvelle(s) tentative(s), " + elapsedMs + " ms");
        return true;
    }

    /**
     * Same working schedule as src/forex_bot/history/calendar.py: trading day = date of (New York
     * time + 7 h); no trading day on Saturday or Sunday (closure Friday 17:00 to Sunday 17:00 New
     * York); 25 December and 1 January are probable holidays. Only hours expected open are retried
     * when empty; empty hours of a probable holiday are accepted as they are and flagged later by
     * the quality report.
     */
    static boolean expectedOpen(long hourStartMs) {
        LocalDate tradingDay = Instant.ofEpochMilli(hourStartMs).atZone(NEW_YORK).plusHours(7).toLocalDate();
        DayOfWeek dow = tradingDay.getDayOfWeek();
        if (dow == DayOfWeek.SATURDAY || dow == DayOfWeek.SUNDAY) {
            return false;
        }
        int month = tradingDay.getMonthValue();
        int dom = tradingDay.getDayOfMonth();
        return !(month == 12 && dom == 25 || month == 1 && dom == 1);
    }

    /**
     * Deletes the SDK's cached file of one tick hour if it is empty. Layout observed in the SDK cache
     * (not documented): {@code EURUSD/<yyyy>/<month 0-11>/<dd>/<HH>h_ticks.bi5}. Only 0-byte files are
     * deleted: a non-empty cached hour is never touched.
     */
    static void dropEmptyCacheFile(Path cacheDir, long hourStartMs) throws IOException {
        ZonedDateTime t = Instant.ofEpochMilli(hourStartMs).atZone(ZoneOffset.UTC);
        Path file = cacheDir.resolve("EURUSD").resolve(String.format("%04d", t.getYear()))
                .resolve(String.format("%02d", t.getMonthValue() - 1)).resolve(String.format("%02d", t.getDayOfMonth()))
                .resolve(String.format("%02dh_ticks.bi5", t.getHour()));
        if (Files.isRegularFile(file) && Files.size(file) == 0) {
            Files.delete(file);
        }
    }

    static Path dayCsv(Path outDir, LocalDate day) {
        return outDir.resolve(day + ".csv");
    }

    /** Shortest decimal representation of the double, never in scientific notation. */
    static String plain(double value) {
        return BigDecimal.valueOf(value).toPlainString();
    }

    /** Reads only the requested keys; other lines (other credentials) are ignored, never echoed. */
    static Map<String, String> readEnv(Path file, Set<String> keys) throws IOException {
        Map<String, String> values = new HashMap<>();
        if (!Files.isRegularFile(file)) {
            fail("fichier d'environnement introuvable : " + file);
        }
        for (String raw : Files.readAllLines(file, StandardCharsets.UTF_8)) {
            String line = raw.strip();
            if (line.startsWith("export ")) {
                line = line.substring(7).strip();
            }
            int eq = line.indexOf('=');
            if (line.startsWith("#") || eq <= 0) {
                continue;
            }
            String key = line.substring(0, eq).strip();
            if (!keys.contains(key)) {
                continue;
            }
            String value = line.substring(eq + 1).strip();
            if (value.length() >= 2 && (value.startsWith("\"") && value.endsWith("\"")
                    || value.startsWith("'") && value.endsWith("'"))) {
                value = value.substring(1, value.length() - 1);
            }
            values.put(key, value);
        }
        return values;
    }

    static Map<String, String> parseArgs(String[] argv) {
        Map<String, String> args = new HashMap<>();
        for (int i = 0; i < argv.length; i++) {
            if (!argv[i].startsWith("--") || i + 1 >= argv.length) {
                fail("argument invalide : " + argv[i]);
            }
            args.put(argv[i].substring(2), argv[++i]);
        }
        return args;
    }

    static String require(Map<String, String> args, String name) {
        String value = args.get(name);
        if (value == null) {
            fail("argument manquant : --" + name);
        }
        return value;
    }

    static void fail(String message) {
        System.err.println("ÉCHEC : " + message);
        System.exit(2);
    }

    /** Strategy used only to obtain IHistory. It never touches the trading engine. */
    static final class HistoryOnly implements IStrategy {
        final CompletableFuture<IHistory> history = new CompletableFuture<>();

        @Override public void onStart(IContext context) { history.complete(context.getHistory()); }
        @Override public void onTick(Instrument instrument, ITick tick) { }
        @Override public void onBar(Instrument instrument, Period period, IBar askBar, IBar bidBar) { }
        @Override public void onMessage(IMessage message) { }
        @Override public void onAccount(IAccount account) { }
        @Override public void onStop() { }
    }

    /** Line-buffered stream that replaces every secret by [MASQUÉ] before printing. */
    static final class MaskingStream extends PrintStream {
        private final PrintStream target;
        private final List<String> secrets;
        private final java.io.ByteArrayOutputStream line = new java.io.ByteArrayOutputStream();

        MaskingStream(PrintStream target, List<String> secrets) {
            super(OutputStream.nullOutputStream(), true, StandardCharsets.UTF_8);
            this.target = target;
            this.secrets = secrets;
        }

        @Override public synchronized void write(int b) {
            if (b == '\n') {
                target.println(mask(line.toString(StandardCharsets.UTF_8)));
                line.reset();
            } else {
                line.write(b);
            }
        }

        @Override public synchronized void write(byte[] buf, int off, int len) {
            for (int i = off; i < off + len; i++) {
                write(buf[i]);
            }
        }

        @Override public synchronized void flush() {
            if (line.size() > 0) {
                target.print(mask(line.toString(StandardCharsets.UTF_8)));
                line.reset();
            }
            target.flush();
        }

        String mask(String text) {
            for (String secret : secrets) {
                text = text.replace(secret, "[MASQUÉ]");
            }
            return URL_TOKEN.matcher(text).replaceAll("$1=[MASQUÉ]");
        }
    }
}
